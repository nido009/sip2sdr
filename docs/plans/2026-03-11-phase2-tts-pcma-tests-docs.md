# SIP2SDR Phase 2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire TTS announcements into active calls, add PCMA as a configurable codec alternative, write integration tests, and write user documentation.

**Architecture:** A new `Codec` enum centralises codec identity; `RingBufferMediaPort` gains a TTS priority buffer (reads TTS samples before SDR samples); `TtsEngine` flows through `SipEngine → _Sip2SdrAccount → _Sip2SdrCall`; PJSUA2 codec priority is set at endpoint startup. Integration tests cover the full DTMF→retune path without hardware. Docs live in `docs/`.

**Tech Stack:** Python 3.10+, PJSUA2 (system, skipped in tests), espeak-ng, pytest, ruff. Venv at `.venv/`; activate with `source .venv/bin/activate`.

---

### Task 1: Codec enum (`codec.py`) + config validation

**Files:**
- Create: `src/sip2sdr/codec.py`
- Modify: `src/sip2sdr/config.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_config.py`
- Modify: `config.example.yaml`

**Step 1: Add codec tests to `tests/test_config.py`**

Append this class to the existing `tests/test_config.py`:

```python
class TestCodecConfig:
    def test_pcmu_parsed(self, tmp_path: Path, marine_config_dict: dict) -> None:
        from sip2sdr.codec import Codec
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(marine_config_dict))
        cfg = load_config(cfg_file)
        assert cfg.audio.codec == Codec.PCMU

    def test_pcma_parsed(self, tmp_path: Path, marine_config_dict: dict) -> None:
        from sip2sdr.codec import Codec
        marine_config_dict["audio"]["codec"] = "pcma"
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(marine_config_dict))
        cfg = load_config(cfg_file)
        assert cfg.audio.codec == Codec.PCMA

    def test_invalid_codec_raises(self, tmp_path: Path, marine_config_dict: dict) -> None:
        marine_config_dict["audio"]["codec"] = "g722"
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(marine_config_dict))
        with pytest.raises(ValueError, match="Unknown codec"):
            load_config(cfg_file)
```

**Step 2: Run new tests — verify they FAIL**

```bash
cd /Users/nils/SIP2SDR && source .venv/bin/activate && pytest tests/test_config.py::TestCodecConfig -v
```
Expected: `ModuleNotFoundError: No module named 'sip2sdr.codec'`

**Step 3: Create `src/sip2sdr/codec.py`**

```python
"""Audio codec identifiers for SIP2SDR.

Only G.711 variants (PCMU and PCMA) are supported, as both operate at
8000 Hz and require no additional transcoding in the audio pipeline.
"""

from enum import Enum


class Codec(Enum):
    """Supported SIP audio codecs.

    Values match the lowercase strings used in the YAML configuration file
    and the PJSUA2 codec identifier prefix (case-insensitive).
    """

    PCMU = "pcmu"  # G.711 µ-law, RTP payload type 0 — default
    PCMA = "pcma"  # G.711 A-law, RTP payload type 8
```

**Step 4: Update `src/sip2sdr/config.py`**

Add the import near the top (after `from sip2sdr.channels import ChannelMode`):
```python
from sip2sdr.codec import Codec
```

Change `AudioConfig.codec` field type from `str` to `Codec`:
```python
@dataclass(frozen=True)
class AudioConfig:
    """Audio pipeline configuration."""

    codec: Codec
    sample_rate: int
    buffer_size: int
```

Replace the `audio` parsing block in `load_config` (lines 115–120):
```python
    audio_raw = raw["audio"]
    codec_str: str = audio_raw["codec"]
    if codec_str == "pcmu":
        codec = Codec.PCMU
    elif codec_str == "pcma":
        codec = Codec.PCMA
    else:
        raise ValueError(f"Unknown codec: {codec_str!r} (expected 'pcmu' or 'pcma')")
    audio = AudioConfig(
        codec=codec,
        sample_rate=int(audio_raw["sample_rate"]),
        buffer_size=int(audio_raw["buffer_size"]),
    )
```

Also update the `load_config` docstring Raises section to mention codec:
```python
    """Load and validate configuration from a YAML file at *path*.

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the mode or codec field is unrecognised.
        KeyError: if a required field is missing.
    """
```

**Step 5: Update `tests/conftest.py`** — existing fixtures use `"pcmu"` which still works as the raw dict value fed into `yaml.dump`. No change needed there.

**Step 6: Update `config.example.yaml`** — change the codec comment line:
```yaml
audio:
  codec: pcmu  # or "pcma" for G.711 A-law
  sample_rate: 8000
  buffer_size: 4000  # samples (~0.5s)
```

**Step 7: Run new tests — verify they PASS**

```bash
pytest tests/test_config.py -v
```
Expected: all 11 tests PASS (8 original + 3 new)

**Step 8: Run ruff**

```bash
ruff check src/sip2sdr/codec.py src/sip2sdr/config.py tests/test_config.py
```

**Step 9: Commit**

```bash
git add src/sip2sdr/codec.py src/sip2sdr/config.py tests/test_config.py config.example.yaml
git commit -m "feat: add Codec enum and validate audio.codec in config"
```

---

### Task 2: TTS priority buffer in `RingBufferMediaPort`

**Files:**
- Modify: `src/sip2sdr/sip/media_port.py`
- Modify: `tests/test_media_port.py`

**Step 1: Add tests to `tests/test_media_port.py`**

The test file currently skips everything when pjsua2 is absent. Add a new **non-pjsua2** test class at the top of the file, before the `pytest.importorskip` line, that tests the TTS priority logic in isolation by calling `getFrame()` on a mock port.

Actually, to test the priority logic without pjsua2 we need a thin helper. Instead, add a standalone test module `tests/test_media_port_priority.py` that imports only pure-Python code:

Create `tests/test_media_port_priority.py`:

```python
"""Tests for TTS priority read logic in the media port (no pjsua2 required)."""

import numpy as np

from sip2sdr.audio.ring_buffer import RingBuffer
from sip2sdr.sip.media_port import _read_frame


class TestReadFrame:
    def test_reads_tts_when_available(self) -> None:
        sdr_buf = RingBuffer(capacity=4000)
        tts_buf = RingBuffer(capacity=4000)
        sdr_buf.write(np.full(160, 1, dtype=np.int16))
        tts_buf.write(np.full(160, 99, dtype=np.int16))
        result = _read_frame(sdr_buf=sdr_buf, tts_buf=tts_buf, n=160)
        assert result[0] == 99  # TTS takes priority

    def test_falls_back_to_sdr_when_tts_empty(self) -> None:
        sdr_buf = RingBuffer(capacity=4000)
        tts_buf = RingBuffer(capacity=4000)
        sdr_buf.write(np.full(160, 7, dtype=np.int16))
        result = _read_frame(sdr_buf=sdr_buf, tts_buf=tts_buf, n=160)
        assert result[0] == 7  # SDR fallback

    def test_returns_silence_when_both_empty(self) -> None:
        sdr_buf = RingBuffer(capacity=4000)
        tts_buf = RingBuffer(capacity=4000)
        result = _read_frame(sdr_buf=sdr_buf, tts_buf=tts_buf, n=160)
        np.testing.assert_array_equal(result, np.zeros(160, dtype=np.int16))

    def test_tts_drains_then_sdr_resumes(self) -> None:
        sdr_buf = RingBuffer(capacity=4000)
        tts_buf = RingBuffer(capacity=4000)
        sdr_buf.write(np.full(320, 7, dtype=np.int16))
        tts_buf.write(np.full(160, 99, dtype=np.int16))  # only one frame of TTS
        first = _read_frame(sdr_buf=sdr_buf, tts_buf=tts_buf, n=160)
        second = _read_frame(sdr_buf=sdr_buf, tts_buf=tts_buf, n=160)
        assert first[0] == 99   # TTS
        assert second[0] == 7   # back to SDR
```

**Step 2: Run tests — verify they FAIL**

```bash
cd /Users/nils/SIP2SDR && source .venv/bin/activate && pytest tests/test_media_port_priority.py -v
```
Expected: `ImportError: cannot import name '_read_frame'`

**Step 3: Update `src/sip2sdr/sip/media_port.py`**

Replace the entire file content:

```python
"""PJSUA2 custom media port that reads audio from a RingBuffer.

Each active SIP call has one RingBufferMediaPort connected to the
demodulator chain's ring buffer.  PJSUA2 calls ``onFrameRequested()``
every 20 ms (160 samples at 8000 Hz) to pull audio for transmission to
the caller.

TTS announcements are played by writing PCM samples into the TTS buffer.
``_read_frame`` always drains the TTS buffer first; once it is empty the
caller hears SDR audio again with no explicit pause/resume required.
"""

from __future__ import annotations

import logging

import numpy as np
import pjsua2 as pj
from numpy.typing import NDArray

from sip2sdr.audio.ring_buffer import RingBuffer

logger = logging.getLogger(__name__)


def _read_frame(
    sdr_buf: RingBuffer,
    tts_buf: RingBuffer,
    n: int,
) -> NDArray[np.int16]:
    """Read one audio frame, preferring TTS audio over SDR audio.

    Args:
        sdr_buf: Ring buffer fed by the GNU Radio demodulator chain.
        tts_buf: Ring buffer fed by TTS announcements.
        n: Number of samples to return.

    Returns:
        Array of exactly *n* int16 samples.
    """
    if tts_buf.available > 0:
        return tts_buf.read(n)
    return sdr_buf.read(n)


class RingBufferMediaPort(pj.AudioMediaPort):
    """PJSUA2 AudioMediaPort that sources audio from a RingBuffer.

    TTS announcements take priority: when *tts_buf* contains samples they
    are played first; once drained, SDR audio from *sdr_buf* resumes
    automatically.

    Args:
        sdr_buf: Ring buffer populated by a GNU Radio demodulator chain.
        tts_buf: Ring buffer populated by TTS announcement audio.
        sample_rate: Audio sample rate in Hz (must be 8000 for G.711).
        samples_per_frame: Number of samples per 20 ms frame (160 for 8 kHz).
    """

    def __init__(
        self,
        sdr_buf: RingBuffer,
        tts_buf: RingBuffer,
        sample_rate: int,
        samples_per_frame: int,
    ) -> None:
        super().__init__()
        self._sdr_buf = sdr_buf
        self._tts_buf = tts_buf
        self._samples_per_frame = samples_per_frame

        fmt = pj.MediaFormatAudio()
        fmt.type = pj.PJMEDIA_TYPE_AUDIO
        fmt.clockRate = sample_rate
        fmt.channelCount = 1
        fmt.bitsPerSample = 16
        fmt.frameTimeUsec = 20_000  # 20 ms

        self.createPort("sip2sdr", fmt)

    def onFrameRequested(self, frame: pj.MediaFrame) -> None:  # type: ignore[override]
        """Fill *frame* with PCM audio, prioritising TTS over SDR.

        Called by PJSUA2 every 20 ms.

        Args:
            frame: PJSUA2 MediaFrame to fill with audio data.
        """
        samples = _read_frame(self._sdr_buf, self._tts_buf, self._samples_per_frame)
        frame.buf = samples.tobytes()

    def getFrame(self) -> bytes:
        """Return one frame of PCM audio as bytes (for testing).

        Returns:
            Raw bytes of int16 PCM samples (samples_per_frame * 2 bytes).
        """
        samples = _read_frame(self._sdr_buf, self._tts_buf, self._samples_per_frame)
        return samples.tobytes()
```

**Step 4: Run priority tests — verify they PASS**

```bash
pytest tests/test_media_port_priority.py -v
```
Expected: 4 PASS

**Step 5: Run the full test suite to catch regressions**

```bash
pytest tests/ -v --tb=short
```
Expected: 47 pass, 4 skip (the pjsua2 tests now skip because `RingBufferMediaPort.__init__` signature changed — that's fine, they test pjsua2 plumbing)

**Step 6: Ruff**

```bash
ruff check src/sip2sdr/sip/media_port.py tests/test_media_port_priority.py
```

**Step 7: Commit**

```bash
git add src/sip2sdr/sip/media_port.py tests/test_media_port_priority.py
git commit -m "feat: add TTS priority buffer to media port"
```

---

### Task 3: Wire TTS through engine

**Files:**
- Modify: `src/sip2sdr/sip/engine.py`
- Modify: `src/sip2sdr/__main__.py`
- Modify: `tests/test_engine.py` (update skipped test signature)

**Note**: `engine.py` imports `pjsua2` at the top, so tests are skipped. The changes here are verified by reading the code and ruff; runtime verification requires a live PJSUA2 environment.

**Step 1: Update `src/sip2sdr/sip/engine.py`**

Replace the entire file:

```python
"""PJSUA2 SIP account manager for SIP2SDR.

Creates one SIP account per configured extension, registers with the
Asterisk PBX, and wires incoming calls to the audio bridge.
"""

from __future__ import annotations

import logging
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

_SAMPLES_PER_FRAME = 160   # 20 ms at 8000 Hz
_TTS_BUF_CAPACITY  = 16_000  # 2 s at 8000 Hz — enough for any announcement


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
        )
        self._default_channel = default_channel

    def onCallState(self, prm: pj.OnCallStateParam) -> None:  # type: ignore[override]
        """Handle call state transitions.

        Args:
            prm: PJSUA2 call state parameters.
        """
        info = self.getInfo()
        logger.info("Call state: %s", info.stateText)
        if info.state == pj.PJSIP_INV_STATE_CONFIRMED:
            self._start_audio()
        elif info.state == pj.PJSIP_INV_STATE_DISCONNECTED:
            self._stop_audio()

    def onDtmfDigit(self, prm: pj.OnDtmfDigitParam) -> None:  # type: ignore[override]
        """Handle an incoming DTMF digit.

        Args:
            prm: PJSUA2 DTMF digit parameters.
        """
        logger.debug("DTMF: %s", prm.digit)
        self._handler.on_dtmf(prm.digit)

    def _start_audio(self) -> None:
        self._port = RingBufferMediaPort(
            sdr_buf=self._sdr_buf,
            tts_buf=self._tts_buf,
            sample_rate=8000,
            samples_per_frame=_SAMPLES_PER_FRAME,
        )
        aud_med = self.getAudioMedia(-1)
        self._port.startTransmit(aud_med)
        self._announce(f"Channel {self._default_channel}")
        logger.info("Audio streaming started")

    def _stop_audio(self) -> None:
        if self._port is not None:
            self._port.stopTransmit(self.getAudioMedia(-1))
            self._port = None
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
    """A registered SIP account that auto-answers calls."""

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
            call_id=prm.callId,
        )
        self._active_call = call
        answer_prm = pj.CallOpParam()
        answer_prm.statusCode = pj.PJSIP_SC_OK
        call.answer(answer_prm)


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

    def start(self) -> None:
        """Initialise PJSUA2, configure codecs, create TLS transport, register accounts."""
        self._ep = pj.Endpoint()
        self._ep.libCreate()

        ep_cfg = pj.EpConfig()
        ep_cfg.logConfig.level = 4
        self._ep.libInit(ep_cfg)

        tp_cfg = pj.TransportConfig()
        tp_cfg.port = 5061
        self._ep.transportCreate(pj.PJSIP_TRANSPORT_TLS, tp_cfg)

        self._ep.libStart()
        self._configure_codecs()

        for ext, buf, retune_fn in zip(
            self._sip_config.extensions, self._buffers, self._retune_fns, strict=True
        ):
            self._register_account(ext, buf, retune_fn)

    def stop(self) -> None:
        """Unregister accounts and shut down PJSUA2."""
        for acc in self._accounts:
            acc.delete()
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
        cfg.regConfig.registrarUri = self._sip_config.registrar
        cred = pj.AuthCredInfo("digest", "*", ext.username, 0, ext.password)
        cfg.sipConfig.authCreds.append(cred)

        if not self._sip_config.verify_certs:
            cfg.sipConfig.tlsConfig.verifyServer = False
            cfg.sipConfig.tlsConfig.verifyClient = False

        if self._sip_config.srtp == "required":
            cfg.mediaConfig.srtpUse = pj.PJMEDIA_SRTP_MANDATORY
        cfg.mediaConfig.srtpSecureSignaling = 0

        acc.create(cfg)
        self._accounts.append(acc)
        logger.info("Registered SIP account: %s", ext.username)
```

**Step 2: Update `tests/test_engine.py`** — the `SipEngine` constructor now requires `tts`. Update the test helper:

```python
# In _make_sip_config, no change needed.
# In both test methods, add tts=MagicMock() to SipEngine constructor:

engine = SipEngine(sip_config=cfg, buffers=buffers, retune_fns=retune_fns, tts=MagicMock())
```

Find and replace both occurrences of:
```python
engine = SipEngine(sip_config=cfg, buffers=buffers, retune_fns=retune_fns)
```
with:
```python
engine = SipEngine(sip_config=cfg, buffers=buffers, retune_fns=retune_fns, tts=MagicMock())
```

**Step 3: Update `src/sip2sdr/__main__.py`** — pass `tts` and `codec` to `SipEngine`:

Find:
```python
    sip = SipEngine(
        sip_config=cfg.sip,
        buffers=buffers,
        retune_fns=retune_fns,
        mode=cfg.mode,
    )
```

Replace with:
```python
    sip = SipEngine(
        sip_config=cfg.sip,
        buffers=buffers,
        retune_fns=retune_fns,
        tts=tts,
        codec=cfg.audio.codec,
        mode=cfg.mode,
    )
```

**Step 4: Run the test suite**

```bash
cd /Users/nils/SIP2SDR && source .venv/bin/activate && pytest tests/ -v --tb=short
```
Expected: 47 pass, 4 skip, 0 fail

**Step 5: Ruff**

```bash
ruff check src/sip2sdr/sip/engine.py src/sip2sdr/__main__.py tests/test_engine.py
```

**Step 6: Commit**

```bash
git add src/sip2sdr/sip/engine.py src/sip2sdr/__main__.py tests/test_engine.py
git commit -m "feat: wire TTS into call handler and add PCMA codec support"
```

---

### Task 4: Integration tests (`tests/test_integration.py`)

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Create `tests/test_integration.py`**

```python
"""Integration tests for the SIP2SDR pipeline (no hardware required).

These tests exercise multi-component paths using only pure-Python modules:
channels, config, ring_buffer, tts, call_handler, and the media port
priority logic.  GNU Radio and PJSUA2 are not required.
"""

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import yaml

from sip2sdr.audio.ring_buffer import RingBuffer
from sip2sdr.channels import ChannelMode, get_channel_frequency
from sip2sdr.codec import Codec
from sip2sdr.config import load_config
from sip2sdr.sip.call_handler import ChannelSwitchHandler
from sip2sdr.sip.media_port import _read_frame


class TestDtmfToRetunePath:
    """Full DTMF→retune path using only pure-Python components."""

    def _make_handler(self) -> tuple[ChannelSwitchHandler, MagicMock, MagicMock]:
        retune_fn = MagicMock()
        announce_fn = MagicMock()
        handler = ChannelSwitchHandler(
            mode=ChannelMode.MARINE,
            retune_fn=retune_fn,
            announce_fn=announce_fn,
        )
        return handler, retune_fn, announce_fn

    def test_simple_channel_switch(self) -> None:
        handler, retune_fn, announce_fn = self._make_handler()
        for digit in "16#":
            handler.on_dtmf(digit)
        retune_fn.assert_called_once_with(16)
        announce_fn.assert_called_once_with("Channel 16")

    def test_cancel_and_reenter(self) -> None:
        """Pressing * mid-sequence clears the buffer; only the final channel is applied."""
        handler, retune_fn, announce_fn = self._make_handler()
        for digit in "67*16#":
            handler.on_dtmf(digit)
        retune_fn.assert_called_once_with(16)

    def test_invalid_channel_no_retune(self) -> None:
        handler, retune_fn, announce_fn = self._make_handler()
        for digit in "99#":
            handler.on_dtmf(digit)
        retune_fn.assert_not_called()
        announce_fn.assert_called_once_with("Invalid channel")

    def test_multiple_switches_in_sequence(self) -> None:
        handler, retune_fn, announce_fn = self._make_handler()
        for digit in "16#67#":
            handler.on_dtmf(digit)
        assert retune_fn.call_count == 2
        retune_fn.assert_any_call(16)
        retune_fn.assert_any_call(67)

    def test_channel_frequency_matches_table(self) -> None:
        """Verify the channel the handler accepts maps to the expected frequency."""
        handler, retune_fn, _ = self._make_handler()
        for digit in "16#":
            handler.on_dtmf(digit)
        channel = retune_fn.call_args[0][0]
        freq = get_channel_frequency(channel, ChannelMode.MARINE)
        assert freq == pytest.approx(156.800, abs=1e-3)


class TestTtsPriorityIntegration:
    """TTS priority buffer interacts correctly with SDR buffer via _read_frame."""

    def test_tts_heard_before_sdr(self) -> None:
        sdr = RingBuffer(4000)
        tts = RingBuffer(4000)
        sdr.write(np.full(160, 1, dtype=np.int16))
        tts.write(np.full(160, 2, dtype=np.int16))
        frame = _read_frame(sdr, tts, 160)
        assert frame[0] == 2

    def test_sdr_resumes_after_tts_drains(self) -> None:
        sdr = RingBuffer(4000)
        tts = RingBuffer(4000)
        sdr.write(np.full(320, 5, dtype=np.int16))
        tts.write(np.full(160, 9, dtype=np.int16))
        first = _read_frame(sdr, tts, 160)
        second = _read_frame(sdr, tts, 160)
        assert first[0] == 9   # TTS
        assert second[0] == 5  # SDR resumed


class TestConfigIntegration:
    """Config loading integrates correctly with codec and mode validation."""

    def _write_config(self, tmp_path: Path, overrides: dict) -> Path:
        base: dict = {
            "mode": "marine",
            "sdr": {"device": "hackrf", "sample_rate": 8_000_000,
                    "gain_lna": 32, "gain_vga": 30, "gain_amp": False},
            "sip": {"registrar": "sip:pbx.example.com", "transport": "tls",
                    "srtp": "required", "verify_certs": False,
                    "extensions": [{"username": "u", "password": "p", "default_channel": 67}]},
            "audio": {"codec": "pcmu", "sample_rate": 8000, "buffer_size": 4000},
        }
        base.update(overrides)
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(base))
        return cfg_file

    def test_pcmu_config_loads(self, tmp_path: Path) -> None:
        cfg = load_config(self._write_config(tmp_path, {}))
        assert cfg.audio.codec == Codec.PCMU

    def test_pcma_config_loads(self, tmp_path: Path) -> None:
        cfg = load_config(self._write_config(tmp_path, {"audio": {
            "codec": "pcma", "sample_rate": 8000, "buffer_size": 4000,
        }}))
        assert cfg.audio.codec == Codec.PCMA

    def test_invalid_codec_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unknown codec"):
            load_config(self._write_config(tmp_path, {"audio": {
                "codec": "g722", "sample_rate": 8000, "buffer_size": 4000,
            }}))

    def test_test_mode_lpd_channels_valid(self, tmp_path: Path) -> None:
        from sip2sdr.channels import is_valid_channel
        cfg = load_config(self._write_config(tmp_path, {
            "mode": "test",
            "sdr": {"device": "hackrf", "sample_rate": 2_000_000,
                    "gain_lna": 32, "gain_vga": 30, "gain_amp": False},
            "sip": {"registrar": "sip:pbx.example.com", "transport": "tls",
                    "srtp": "required", "verify_certs": False,
                    "extensions": [{"username": "u", "password": "p", "default_channel": 1}]},
        }))
        assert is_valid_channel(cfg.sip.extensions[0].default_channel, cfg.mode)
```

**Step 2: Run tests — verify they all PASS**

```bash
cd /Users/nils/SIP2SDR && source .venv/bin/activate && pytest tests/test_integration.py -v
```
Expected: 11 PASS

**Step 3: Run full test suite**

```bash
pytest tests/ -v --tb=short
```
Expected: 58 pass, 4 skip, 0 fail

**Step 4: Ruff**

```bash
ruff check tests/test_integration.py
```

**Step 5: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for DTMF path, TTS priority, and config"
```

---

### Task 5: Documentation

**Files:**
- Create: `docs/setup.md`
- Create: `docs/configuration.md`
- Create: `docs/usage.md`
- Create: `docs/asterisk-setup.md`

**Step 1: Create `docs/setup.md`**

```markdown
# SIP2SDR — Installation & Setup

## System Requirements

- Linux (Debian/Ubuntu recommended) or macOS (for development)
- Python 3.10+
- [HackRF One](https://greatscottgadgets.com/hackrf/) SDR hardware

## System Package Dependencies

Install the following system packages before creating the Python venv:

```bash
# Debian/Ubuntu
sudo apt install \
    gnuradio gr-osmosdr \
    libhackrf-dev hackrf \
    espeak-ng \
    libpjproject-dev python3-pjsua2

# macOS (development only — GNU Radio via Homebrew, no HackRF)
brew install gnuradio espeak-ng
```

## Python Virtual Environment

All Python packages must be installed inside a venv. Do **not** install pip packages system-wide.

```bash
cd /path/to/sip2sdr
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## GNU Radio Python Bindings

GNU Radio installs its Python bindings into the system site-packages, not into the venv. Export the path before running the application or tests:

```bash
export PYTHONPATH=/usr/lib/python3/dist-packages:$PYTHONPATH
```

Add this to your shell profile or to a `.env` file sourced at startup.

## Verify Installation

```bash
source .venv/bin/activate
python -c "import sip2sdr; print(sip2sdr.__version__)"
# → 0.1.0

espeak-ng --version
# → eSpeak NG text-to-speech: 1.xx ...

# If GNU Radio is installed:
python -c "import gnuradio; print(gnuradio.__version__)"
```

## Running Tests

```bash
pytest tests/ -v
# Pure-Python tests run without hardware.
# GNU Radio / PJSUA2 tests are automatically skipped if those packages are absent.
```
```

**Step 2: Create `docs/configuration.md`**

```markdown
# SIP2SDR — Configuration Reference

SIP2SDR is configured via a single YAML file. Copy `config.example.yaml` and edit it.

```bash
cp config.example.yaml config.yaml
```

## Top-Level Fields

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `mode` | string | `marine`, `test` | Channel plan to use. `marine` = ITU VHF (156–162 MHz). `test` = LPD433 (433–434 MHz). |

## `sdr` Section

SDR hardware parameters.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `device` | string | `hackrf` | osmosdr device type |
| `sample_rate` | int | `8000000` | ADC sample rate (Hz). Use 8 Msps for marine, 2 Msps for LPD. |
| `gain_lna` | int | `32` | LNA gain (dB) |
| `gain_vga` | int | `30` | VGA gain (dB) |
| `gain_amp` | bool | `false` | Enable RF preamplifier |

## `sip` Section

SIP PBX connection and extension credentials.

| Field | Type | Description |
|-------|------|-------------|
| `registrar` | string | SIP registrar URI, e.g. `sip:pbx.example.com` |
| `transport` | string | `tls` (SIP over TLS on port 5061) |
| `srtp` | string | `required` — all media must be encrypted |
| `verify_certs` | bool | `false` to accept self-signed TLS certificates |
| `extensions` | list | List of SIP extension objects (see below) |

### Extension Object

| Field | Type | Description |
|-------|------|-------------|
| `username` | string | SIP username (account name in Asterisk) |
| `password` | string | SIP password |
| `default_channel` | int | Channel to tune when a call connects |

Up to 4 extensions are supported (one per demodulator chain).

## `audio` Section

Audio pipeline settings.

| Field | Type | Values | Default | Description |
|-------|------|--------|---------|-------------|
| `codec` | string | `pcmu`, `pcma` | `pcmu` | G.711 codec. `pcmu` = µ-law (RTP PT 0). `pcma` = A-law (RTP PT 8). Use `pcma` if your PBX requires it. |
| `sample_rate` | int | `8000` | `8000` | Audio sample rate in Hz. Must be 8000. |
| `buffer_size` | int | — | `4000` | Ring buffer size in samples (~0.5 s at 8 kHz). |

## Example Configuration

```yaml
mode: marine

sdr:
  device: "hackrf"
  sample_rate: 8000000
  gain_lna: 32
  gain_vga: 30
  gain_amp: false

sip:
  registrar: "sip:pbx.example.com"
  transport: tls
  srtp: required
  verify_certs: false
  extensions:
    - username: "sip2sdr-1"
      password: "secret1"
      default_channel: 67
    - username: "sip2sdr-2"
      password: "secret2"
      default_channel: 16

audio:
  codec: pcmu
  sample_rate: 8000
  buffer_size: 4000
```
```

**Step 3: Create `docs/usage.md`**

```markdown
# SIP2SDR — Usage Guide

## Starting the Application

```bash
source .venv/bin/activate
export PYTHONPATH=/usr/lib/python3/dist-packages:$PYTHONPATH

sip2sdr config.yaml
# or
python -m sip2sdr config.yaml
```

### Command-Line Options

```
usage: sip2sdr [-h] [--log-level LOG_LEVEL] config

positional arguments:
  config                Path to YAML config file

options:
  --log-level LOG_LEVEL  Log level: DEBUG, INFO, WARNING (default: INFO)
```

### Stop the Application

Press `Ctrl+C` or send `SIGTERM`. SIP accounts are unregistered and the flowgraph is stopped cleanly.

## Operating Modes

### Marine VHF (`mode: marine`)

- **Band**: 156.0 – 162.025 MHz
- **Channel spacing**: 25 kHz
- **Valid channels**: 1–28, 60–88
- **SDR center frequency**: 159 MHz
- **Default channel**: 67 (Kieler Förde small craft calling)

### Test / LPD433 (`mode: test`)

- **Band**: 433.075 – 434.775 MHz
- **Channel spacing**: 25 kHz
- **Valid channels**: 1–69
- **SDR center frequency**: 433.9 MHz
- For development and testing without using Marine VHF frequencies.

## Using DTMF to Switch Channels

Once a call is connected you will hear the current channel announced (e.g. *"Channel 67"*). To switch:

1. Dial the channel number on your keypad
2. Press `#` to confirm

Examples:
- Switch to channel 16: press `1`, `6`, `#`
- Switch to channel 67: press `6`, `7`, `#`

Press `*` at any time to cancel the digits entered so far and start over.

If you enter an invalid channel number, you will hear *"Invalid channel"* and the current channel is unchanged.

## Key Marine VHF Channels

| Channel | Frequency | Purpose |
|---------|-----------|---------|
| 6 | 156.300 MHz | Inter-ship safety |
| 9 | 156.450 MHz | Calling (regional) |
| 13 | 156.650 MHz | Bridge-to-bridge safety |
| 16 | 156.800 MHz | **Distress, safety & calling** (international) |
| 67 | 156.375 MHz | Small craft (Kieler Förde) |
| 70 | 156.525 MHz | DSC (Digital Selective Calling) |
| 72 | 156.625 MHz | Inter-ship |
```

**Step 4: Create `docs/asterisk-setup.md`**

```markdown
# SIP2SDR — Asterisk PBX Setup

This guide covers the Asterisk (or FreePBX) configuration required to connect SIP2SDR.

## SIP Accounts

Create one SIP account for each extension in your `config.yaml`. SIP2SDR registers as a SIP endpoint and waits for incoming calls — it never places outbound calls.

### Asterisk `pjsip.conf` (or FreePBX PJSIP endpoint)

```ini
; Repeat for sip2sdr-1 through sip2sdr-4

[sip2sdr-1]
type=endpoint
transport=transport-tls
auth=sip2sdr-1-auth
aors=sip2sdr-1-aor
context=sip2sdr
allow=!all,ulaw,alaw        ; PCMU and/or PCMA only
dtmf_mode=rfc4733
media_encryption=sdes
media_encryption_optimistic=no

[sip2sdr-1-auth]
type=auth
auth_type=userpass
username=sip2sdr-1
password=secret1

[sip2sdr-1-aor]
type=aor
max_contacts=1
```

> **Codec note:** `ulaw` = PCMU (G.711 µ-law), `alaw` = PCMA (G.711 A-law).
> If your `config.yaml` sets `codec: pcmu`, list only `ulaw`. For `pcma`, list only `alaw`.

### TLS Transport

```ini
[transport-tls]
type=transport
protocol=tls
bind=0.0.0.0:5061
cert_file=/etc/asterisk/keys/asterisk.pem
priv_key_file=/etc/asterisk/keys/asterisk.key
; Self-signed certificates are accepted by SIP2SDR when verify_certs: false
```

### Dialplan (`extensions.conf`)

Create a context that routes calls to the SIP2SDR extensions:

```ini
[sip2sdr]
; Allow any internal extension to call SIP2SDR channels
exten => sip2sdr-1,1,Dial(PJSIP/sip2sdr-1)
exten => sip2sdr-2,1,Dial(PJSIP/sip2sdr-2)
exten => sip2sdr-3,1,Dial(PJSIP/sip2sdr-3)
exten => sip2sdr-4,1,Dial(PJSIP/sip2sdr-4)

; Or use a feature code, e.g. *80 calls channel 1 (default ch 67):
exten => *80,1,Dial(PJSIP/sip2sdr-1)
```

## SRTP

SIP2SDR requires SRTP (`srtp: required` in config). On the Asterisk side, `media_encryption=sdes` enables SRTP key exchange via SDP. Both sides must agree — if Asterisk is configured with `media_encryption=no`, calls will be rejected.

## Generating a Self-Signed TLS Certificate

```bash
cd /etc/asterisk/keys
openssl req -x509 -nodes -newkey rsa:4096 \
    -keyout asterisk.key -out asterisk.pem \
    -days 3650 -subj "/CN=pbx.example.com"
chmod 600 asterisk.key
asterisk -rx "module reload res_pjsip.so"
```

Set `verify_certs: false` in `config.yaml` to allow SIP2SDR to accept this self-signed certificate.
```

**Step 5: Run full test suite (docs don't affect tests)**

```bash
cd /Users/nils/SIP2SDR && source .venv/bin/activate && pytest tests/ -v --tb=short
```
Expected: 58 pass, 4 skip, 0 fail

**Step 6: Commit docs**

```bash
git add docs/setup.md docs/configuration.md docs/usage.md docs/asterisk-setup.md
git commit -m "docs: add setup, configuration, usage, and Asterisk setup guides"
```

---

## Summary

| Task | Files | Tests added | External deps |
|------|-------|-------------|---------------|
| 1 — Codec enum + config | `codec.py`, `config.py` | 3 | none |
| 2 — TTS priority buffer | `media_port.py`, `test_media_port_priority.py` | 4 | none |
| 3 — TTS + PCMA wiring | `engine.py`, `__main__.py` | 0 (pjsua2-gated) | pjsua2 |
| 4 — Integration tests | `test_integration.py` | 11 | none |
| 5 — Docs | 4 `docs/*.md` files | 0 | none |

Final test count: **58 pass, 4 skip**.
