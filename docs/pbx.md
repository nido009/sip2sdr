# PJSUA2 + Asterisk PBX Integration — Lessons Learned

Reference for building SIP voice agents in Python using pjsua2, based on hands-on
integration with an Asterisk PBX (wavelab.ipv.astimax.de) over SIP-TLS + SRTP.

---

## Environment

- **pjsua2 version**: 2.15.1 (built from source — not available in Ubuntu 24.04 apt repos)
- **Python**: 3.12
- **OS**: Ubuntu 24.04
- **PBX**: Asterisk 6 (self-hosted, IP 212.51.30.137)
- **Transport**: SIP-TLS on port 5061, SRTP mandatory

---

## Building pjsua2 from Source (Ubuntu 24.04)

No distro package exists. Must build from source:

```bash
# Install build deps
sudo apt-get install -y build-essential python3-dev libssl-dev \
    libopus-dev libportaudio2 libportaudiocpp0 portaudio19-dev swig

# Download pjproject 2.15.1 (NOT 2.14.x — incompatible with SWIG 4.2)
wget https://github.com/pjsip/pjproject/archive/refs/tags/2.15.1.tar.gz
tar xzf 2.15.1.tar.gz && cd pjproject-2.15.1

# Build C library (disable video for headless servers)
./configure --enable-shared --disable-video --disable-opencore-amr
make dep -j$(nproc) && make -j$(nproc)
sudo make install && sudo ldconfig

# Build Python bindings
cd pjsip-apps/src/swig/python && make

# Install into venv
cp build/lib.linux-x86_64-cpython-312/_pjsua2.cpython-312-x86_64-linux-gnu.so \
    /path/to/.venv/lib/python3.12/site-packages/
cp pjsua2.py /path/to/.venv/lib/python3.12/site-packages/
```

**Version compatibility**: pjproject 2.14.x fails to compile Python bindings with
SWIG 4.2 (`SwigPyMapIterator_T` type conversion error). Use 2.15.1+.

---

## Initialising the Endpoint

```python
import pjsua2 as pj

ep = pj.Endpoint()
ep.libCreate()

ep_cfg = pj.EpConfig()
ep_cfg.logConfig.level = 4  # 5 = verbose, 4 = info, 3 = warnings only
ep.libInit(ep_cfg)

# CRITICAL on headless servers: set null audio device BEFORE creating accounts.
# Without this, any call that connects will fail with:
#   PJMEDIA_EAUD_NODEFDEV "Unable to find default audio device"
# All audio goes through custom AudioMediaPort — no physical sound card needed.
ep.libStart()
ep.audDevManager().setNullDev()
```

---

## TLS Transport

```python
tp_cfg = pj.TransportConfig()
tp_cfg.port = 5061

# TLS verification — set on TransportConfig.tlsConfig, NOT AccountSipConfig
# (AccountSipConfig does NOT have a tlsConfig attribute in 2.15.1)
tp_cfg.tlsConfig.verifyServer = False  # for self-signed certs
tp_cfg.tlsConfig.verifyClient = False

ep.transportCreate(pj.PJSIP_TRANSPORT_TLS, tp_cfg)
```

---

## Registering a SIP Account

```python
cfg = pj.AccountConfig()

# Identity URI
cfg.idUri = "sip:username@pbx.example.com"

# Registrar — MUST append ;transport=tls for TLS accounts.
# Without this, pjsua2 fails with PJSIP_EUNSUPTRANSPORT
# ("Unable to generate suitable Contact header for registration")
cfg.regConfig.registrarUri = "sip:pbx.example.com;transport=tls"

# SIP digest authentication
cred = pj.AuthCredInfo("digest", "*", "username", 0, "password")
cfg.sipConfig.authCreds.append(cred)

# SRTP — mandatory means the call will fail if SRTP can't be negotiated
cfg.mediaConfig.srtpUse = pj.PJMEDIA_SRTP_MANDATORY
cfg.mediaConfig.srtpSecureSignaling = 0  # allow SRTP on plain SIP signalling

account.create(cfg)
```

---

## Account Lifecycle

```python
# Shutdown (not delete — Account.delete() does not exist in 2.15.1)
account.shutdown()

# Destroy the endpoint
ep.libDestroy()
```

---

## Codec Priority

Set after `libStart()`, before accounts are created:

```python
# Prefer PCMA (G.711 A-law, payload type 8)
ep.codecSetPriority("PCMA/8000", 255)
ep.codecSetPriority("PCMU/8000", 0)

# Or prefer PCMU (G.711 µ-law, payload type 0) — the default
ep.codecSetPriority("PCMU/8000", 255)
ep.codecSetPriority("PCMA/8000", 0)
```

The strings must match exactly what pjsua2 registers. For G.711:
`"PCMU/8000"` and `"PCMA/8000"`. PJSUA2 silently ignores unknown codec IDs.

---

## Custom Audio Media Port

The key to routing custom audio (from a ring buffer, file, generator, etc.) into
a SIP call without a sound card:

```python
class MyMediaPort(pj.AudioMediaPort):
    def __init__(self, sample_rate: int = 8000, samples_per_frame: int = 160):
        super().__init__()
        fmt = pj.MediaFormatAudio()
        fmt.type = pj.PJMEDIA_TYPE_AUDIO
        fmt.clockRate = sample_rate      # 8000 Hz for G.711
        fmt.channelCount = 1             # mono
        fmt.bitsPerSample = 16           # int16 PCM
        fmt.frameTimeUsec = 20_000       # 20 ms frames
        self.createPort("myport", fmt)

    def onFrameRequested(self, frame: pj.MediaFrame) -> None:
        # Called by PJSUA2 every 20 ms to pull audio for the caller.
        # frame.buf is a pj.ByteVector — cannot assign bytes directly.
        # Must use resize() + slice assignment:
        raw: bytes = self._get_audio_bytes(160)  # 160 int16 = 320 bytes
        frame.buf.resize(len(raw))
        frame.buf[:] = list(raw)         # list(bytes) gives list of ints 0-255
```

**Critical**: `frame.buf = samples.tobytes()` raises `TypeError` in pjsua2 2.15.1.
`frame.buf` is a `pj::ByteVector *` and requires the resize+slice pattern above.

---

## Connecting Media Port to Call Audio

In the call's `onCallState` callback, when state is `PJSIP_INV_STATE_CONFIRMED`:

```python
def _start_audio(self) -> None:
    self._port = MyMediaPort()
    aud_med = self.getAudioMedia(-1)   # -1 = first audio stream
    self._port.startTransmit(aud_med)  # port → caller (TX)
    # For receiving audio from caller into port:
    # aud_med.startTransmit(self._port)
```

When disconnecting (`PJSIP_INV_STATE_DISCONNECTED`):

```python
def _stop_audio(self) -> None:
    if self._port is not None:
        try:
            self._port.stopTransmit(self.getAudioMedia(-1))
        except pj.Error:
            # getAudioMedia(-1) can raise in DISCONNECTED state
            # if media session is already torn down — safe to ignore
            pass
        self._port = None
```

---

## DTMF

DTMF digits arrive in `onDtmfDigit()` on the `pj.Call` subclass:

```python
def onDtmfDigit(self, prm: pj.OnDtmfDigitParam) -> None:
    digit = prm.digit  # single character: "0"-"9", "*", "#"
```

Asterisk sends DTMF via RFC 4733 (telephone-event RTP) by default.

---

## Call Handler Pattern

```python
class MyCall(pj.Call):
    def __init__(self, account: pj.Account, call_id: int = pj.PJSUA_INVALID_ID):
        super().__init__(account, call_id)

    def onCallState(self, prm: pj.OnCallStateParam) -> None:
        info = self.getInfo()
        if info.state == pj.PJSIP_INV_STATE_CONFIRMED:
            self._start_audio()
        elif info.state == pj.PJSIP_INV_STATE_DISCONNECTED:
            self._stop_audio()

class MyAccount(pj.Account):
    def onIncomingCall(self, prm: pj.OnIncomingCallParam) -> None:
        call = MyCall(self, prm.callId)
        call_prm = pj.CallOpParam()
        call_prm.statusCode = pj.PJSIP_SC_OK  # auto-answer
        call.answer(call_prm)
```

---

## Asterisk Keepalives

Once registered, Asterisk sends periodic `OPTIONS` requests to each extension
to check availability. pjsua2 responds to these automatically — no application
code required. This is normal and expected in the logs.

---

## Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `PJSIP_EUNSUPTRANSPORT` on registration | Registrar URI uses `sip:` but TLS transport active | Append `;transport=tls` to registrar URI |
| `PJMEDIA_EAUD_NODEFDEV` on call connect | No physical sound card, pjsua2 tries to open one | Call `ep.audDevManager().setNullDev()` after `libStart()` |
| `TypeError: argument 2 of type 'pj::ByteVector *'` | `frame.buf = bytes` not accepted in 2.15.1 | Use `frame.buf.resize(n); frame.buf[:] = list(raw)` |
| `AttributeError: 'AccountSipConfig' object has no attribute 'tlsConfig'` | TLS config is on `TransportConfig`, not `AccountSipConfig` | Set `tp_cfg.tlsConfig.verifyServer = False` on the transport |
| `Account.delete()` AttributeError | Method renamed in 2.15.1 | Use `account.shutdown()` |
| `pm_remez: insufficient extremals` | GNU Radio `fm_demod_cf` given full SDR sample rate (2+ Msps) | Decimate in `freq_xlating_fir_filter` first; pass decimated rate (~50 kHz) to `fm_demod_cf` |
| `Failed to open HackRF device: Resource busy` | Previous process still holding USB device | Kill previous process; USB device releases automatically on clean exit |

---

## Audio Format for G.711

- **Sample rate**: 8000 Hz
- **Channels**: 1 (mono)
- **Bit depth**: 16-bit signed PCM (int16)
- **Frame size**: 160 samples = 20 ms = 320 bytes
- **Silence**: `np.zeros(160, dtype=np.int16)`

Both PCMU and PCMA encode 8-bit on the wire but pjsua2 works with 16-bit PCM
internally. The codec conversion is handled by pjsua2 transparently.

---

## Thread Safety Notes

- `onFrameRequested` runs on a pjsua2 internal thread — any shared state
  accessed here must be thread-safe.
- `onCallState` and `onDtmfDigit` also run on pjsua2 threads.
- Avoid long-blocking calls (e.g. `subprocess.run`) in pjsua2 callbacks — use
  a background thread or pre-generate data.
- GNU Radio runs its own scheduler threads. Use a thread-safe ring buffer
  (e.g. with `threading.Lock`) between GNU Radio sinks and pjsua2 ports.

---

## Shutdown Order

1. `account.shutdown()` for each account
2. `ep.libDestroy()`
3. `flowgraph.stop()` / `flowgraph.wait()` for GNU Radio

Stopping GNU Radio *after* pjsua2 avoids the `terminate reached from thread id`
crash that occurs when Python exits while GR scheduler threads are still active.
