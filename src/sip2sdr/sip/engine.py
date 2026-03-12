"""PJSUA2 SIP account manager for SIP2SDR.

Creates one SIP account per configured extension, registers with the
Asterisk PBX, and wires incoming calls to the audio bridge.

Each account tracks observable state (call status, current channel,
DTMF history) accessible via ``get_account_states()``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import pjsua2 as pj

from sip2sdr.audio.ring_buffer import RingBuffer
from sip2sdr.audio.tts import TtsEngine
from sip2sdr.channels import ChannelMode
from sip2sdr.codec import Codec
from sip2sdr.config import ExtensionConfig, SipConfig
from sip2sdr.sip.call_handler import ChannelSwitchHandler
from sip2sdr.sip.media_port import RingBufferMediaPort

logger = logging.getLogger(__name__)

_SAMPLES_PER_FRAME = 160    # 20 ms at 8000 Hz
_TTS_BUF_CAPACITY  = 16_000  # 2 s at 8000 Hz — enough for any announcement
_DTMF_HISTORY_MAX  = 20     # keep at most this many entries per account


class _Sip2SdrCall(pj.Call):
    """A single active SIP call with audio streaming and DTMF handling."""

    def __init__(
        self,
        account: pj.Account,
        sdr_buf: RingBuffer,
        tts: TtsEngine,
        retune_fn: Callable[[int], None],
        mode: ChannelMode,
        default_channel: int,
        on_call_started_fn: Callable[[str], None],
        on_call_ended_fn: Callable[[], None],
        dtmf_event_fn: Callable[[str], None],
        channel_switch_fn: Callable[[int], None],
        call_id: int = pj.PJSUA_INVALID_ID,
    ) -> None:
        super().__init__(account, call_id)
        self._sdr_buf = sdr_buf
        self._tts = tts
        self._tts_buf = RingBuffer(capacity=_TTS_BUF_CAPACITY)
        self._port: RingBufferMediaPort | None = None
        self._handler = ChannelSwitchHandler(
            mode=mode,
            retune_fn=retune_fn,
            announce_fn=self._announce,
            dtmf_event_fn=dtmf_event_fn,
            channel_switch_fn=channel_switch_fn,
        )
        self._default_channel = default_channel
        self._on_call_started_fn = on_call_started_fn
        self._on_call_ended_fn = on_call_ended_fn

    def onCallState(self, prm: pj.OnCallStateParam) -> None:  # type: ignore[override]
        """Handle call state transitions.

        Args:
            prm: PJSUA2 call state parameters.
        """
        info = self.getInfo()
        logger.info("Call state: %s", info.stateText)
        if info.state == pj.PJSIP_INV_STATE_CONFIRMED:
            self._start_audio(info.remoteUri)
        elif info.state == pj.PJSIP_INV_STATE_DISCONNECTED:
            self._stop_audio()

    def onDtmfDigit(self, prm: pj.OnDtmfDigitParam) -> None:  # type: ignore[override]
        """Handle an incoming DTMF digit.

        Args:
            prm: PJSUA2 DTMF digit parameters.
        """
        logger.debug("DTMF: %s", prm.digit)
        self._handler.on_dtmf(prm.digit)

    def _start_audio(self, remote_uri: str) -> None:
        self._port = RingBufferMediaPort(
            sdr_buf=self._sdr_buf,
            tts_buf=self._tts_buf,
            sample_rate=8000,
            samples_per_frame=_SAMPLES_PER_FRAME,
        )
        aud_med = self.getAudioMedia(-1)
        self._port.startTransmit(aud_med)
        self._on_call_started_fn(remote_uri)
        self._announce(f"Channel {self._default_channel}")
        logger.info("Audio streaming started")

    def _stop_audio(self) -> None:
        if self._port is not None:
            try:
                self._port.stopTransmit(self.getAudioMedia(-1))
            except pj.Error:
                # Media may already be invalid in DISCONNECTED state
                logger.debug("Media already torn down during _stop_audio")
            self._port = None
        self._on_call_ended_fn()
        logger.info("Audio streaming stopped")

    def _announce(self, text: str) -> None:
        """Generate TTS for *text* and write it into the TTS priority buffer.

        Args:
            text: Announcement text, e.g. ``"Channel 67"`` or ``"Invalid channel"``.
        """
        logger.info("Announcement: %s", text)
        pcm = self._tts.generate(text)
        self._tts_buf.write(pcm)


class _Sip2SdrAccount(pj.Account):
    """A registered SIP account that auto-answers calls and tracks observable state."""

    def __init__(
        self,
        sdr_buf: RingBuffer,
        tts: TtsEngine,
        retune_fn: Callable[[int], None],
        mode: ChannelMode,
        default_channel: int,
    ) -> None:
        super().__init__()
        self._sdr_buf = sdr_buf
        self._tts = tts
        self._retune_fn = retune_fn
        self._mode = mode
        self._default_channel = default_channel
        self._active_call: _Sip2SdrCall | None = None

        # Observable state
        self._is_in_call: bool = False
        self._remote_uri: str = ""
        self._call_start_time: float | None = None
        self._current_channel: int = default_channel
        self._dtmf_history: list[tuple[str, float]] = []

    def onIncomingCall(self, prm: pj.OnIncomingCallParam) -> None:  # type: ignore[override]
        """Auto-answer an incoming call and start audio streaming.

        Args:
            prm: PJSUA2 incoming call parameters.
        """
        logger.info("Incoming call (id=%d)", prm.callId)
        call = _Sip2SdrCall(
            account=self,
            sdr_buf=self._sdr_buf,
            tts=self._tts,
            retune_fn=self._retune_fn,
            mode=self._mode,
            default_channel=self._default_channel,
            on_call_started_fn=self._on_call_started,
            on_call_ended_fn=self._on_call_ended,
            dtmf_event_fn=self._record_dtmf,
            channel_switch_fn=self._on_channel_switch,
            call_id=prm.callId,
        )
        self._active_call = call
        answer_prm = pj.CallOpParam()
        answer_prm.statusCode = pj.PJSIP_SC_OK
        call.answer(answer_prm)

    def get_state(self) -> dict:
        """Return current observable state for this account.

        Returns:
            Dict with keys: ``is_in_call``, ``remote_uri``,
            ``call_duration_s``, ``current_channel``, ``dtmf_history``.
        """
        duration = (
            time.time() - self._call_start_time
            if self._call_start_time is not None
            else 0.0
        )
        return {
            "is_in_call": self._is_in_call,
            "remote_uri": self._remote_uri,
            "call_duration_s": duration,
            "current_channel": self._current_channel,
            "dtmf_history": list(self._dtmf_history),
        }

    def _on_call_started(self, remote_uri: str) -> None:
        self._is_in_call = True
        self._remote_uri = remote_uri
        self._call_start_time = time.time()
        self._current_channel = self._default_channel

    def _on_call_ended(self) -> None:
        self._is_in_call = False
        self._remote_uri = ""
        self._call_start_time = None
        self._active_call = None

    def _record_dtmf(self, digit: str) -> None:
        self._dtmf_history.append((digit, time.time()))
        if len(self._dtmf_history) > _DTMF_HISTORY_MAX:
            self._dtmf_history = self._dtmf_history[-_DTMF_HISTORY_MAX:]

    def _on_channel_switch(self, channel: int) -> None:
        self._current_channel = channel


class SipEngine:
    """Manages PJSUA2 library lifecycle and SIP accounts.

    Args:
        sip_config: SIP configuration (registrar, transport, extensions).
        buffers: One SDR ring buffer per extension.
        retune_fns: One retune callable per extension.
        tts: TTS engine used to generate channel announcements.
        codec: Audio codec to negotiate with the PBX (PCMU or PCMA).
        mode: Operating mode for DTMF channel validation.
    """

    def __init__(
        self,
        sip_config: SipConfig,
        buffers: list[RingBuffer],
        retune_fns: list[Callable[[int], None]],
        tts: TtsEngine,
        codec: Codec = Codec.PCMU,
        mode: ChannelMode = ChannelMode.MARINE,
    ) -> None:
        self._sip_config = sip_config
        self._buffers = buffers
        self._retune_fns = retune_fns
        self._tts = tts
        self._codec = codec
        self._mode = mode
        self._accounts: list[_Sip2SdrAccount] = []
        self._ep: pj.Endpoint | None = None

    @property
    def num_extensions(self) -> int:
        """Number of SIP extensions configured."""
        return len(self._sip_config.extensions)

    def get_account_states(self) -> list[dict]:
        """Return current observable state for all SIP accounts.

        Returns:
            List of dicts (one per account), each containing:
            ``is_in_call``, ``remote_uri``, ``call_duration_s``,
            ``current_channel``, ``dtmf_history``.
        """
        return [acc.get_state() for acc in self._accounts]

    def start(self) -> None:
        """Initialise PJSUA2, configure codecs, create TLS transport, register accounts."""
        self._ep = pj.Endpoint()
        self._ep.libCreate()

        ep_cfg = pj.EpConfig()
        ep_cfg.logConfig.level = 4
        self._ep.libInit(ep_cfg)

        tp_cfg = pj.TransportConfig()
        tp_cfg.port = 5061
        if not self._sip_config.verify_certs:
            tp_cfg.tlsConfig.verifyServer = False
            tp_cfg.tlsConfig.verifyClient = False
        self._ep.transportCreate(pj.PJSIP_TRANSPORT_TLS, tp_cfg)

        self._ep.libStart()
        # Use null audio device — the server has no sound card; all audio goes
        # through our custom RingBufferMediaPort connected to the conference bridge.
        self._ep.audDevManager().setNullDev()
        self._configure_codecs()

        for ext, buf, retune_fn in zip(
            self._sip_config.extensions, self._buffers, self._retune_fns, strict=True
        ):
            self._register_account(ext, buf, retune_fn)

    def stop(self) -> None:
        """Unregister accounts and shut down PJSUA2."""
        for acc in self._accounts:
            acc.shutdown()
        self._accounts.clear()
        if self._ep is not None:
            self._ep.libDestroy()
            self._ep = None

    def _configure_codecs(self) -> None:
        """Set PJSUA2 endpoint codec priorities based on configured codec.

        The preferred codec is raised to priority 255; the other G.711
        variant is lowered to 0 so the PBX negotiates the correct one.
        """
        assert self._ep is not None
        if self._codec == Codec.PCMA:
            self._ep.codecSetPriority("PCMA/8000", 255)
            self._ep.codecSetPriority("PCMU/8000", 0)
            logger.info("Codec priority: PCMA preferred")
        else:
            self._ep.codecSetPriority("PCMU/8000", 255)
            self._ep.codecSetPriority("PCMA/8000", 0)
            logger.info("Codec priority: PCMU preferred")

    def _register_account(
        self,
        ext: ExtensionConfig,
        buf: RingBuffer,
        retune_fn: Callable[[int], None],
    ) -> None:
        acc = _Sip2SdrAccount(
            sdr_buf=buf,
            tts=self._tts,
            retune_fn=retune_fn,
            mode=self._mode,
            default_channel=ext.default_channel,
        )
        cfg = pj.AccountConfig()
        cfg.idUri = f"sip:{ext.username}@{self._sip_config.registrar.removeprefix('sip:')}"
        # Append ;transport=tls so PJSUA2 uses the TLS transport for registration
        registrar = self._sip_config.registrar
        if not registrar.endswith(";transport=tls"):
            registrar += ";transport=tls"
        cfg.regConfig.registrarUri = registrar
        cred = pj.AuthCredInfo("digest", "*", ext.username, 0, ext.password)
        cfg.sipConfig.authCreds.append(cred)

        if self._sip_config.srtp == "required":
            cfg.mediaConfig.srtpUse = pj.PJMEDIA_SRTP_MANDATORY
        cfg.mediaConfig.srtpSecureSignaling = 0

        acc.create(cfg)
        self._accounts.append(acc)
        logger.info("Registered SIP account: %s", ext.username)
