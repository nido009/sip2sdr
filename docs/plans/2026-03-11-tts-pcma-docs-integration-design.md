# SIP2SDR Phase 2 Design: TTS Wiring, PCMA Codec, Integration Tests, Docs

## TTS Wiring

### Problem
`_Sip2SdrCall._announce()` is a stub. `TtsEngine` is instantiated in `__main__.py` but never passed to the SIP layer.

### Design
Add a **TTS priority buffer** (second `RingBuffer`) per call alongside the existing SDR ring buffer. `RingBufferMediaPort` reads from the TTS buffer first (if samples available), otherwise falls back to the SDR buffer. The `_announce()` method writes TTS PCM into the TTS buffer.

GNU Radio continues writing to the SDR buffer uninterrupted. SDR audio resumes automatically once the TTS buffer drains — no explicit pause/resume, no locking, no timing.

**Wiring chain**: `__main__.py` → `SipEngine(tts=...)` → `_Sip2SdrAccount(tts=...)` → `_Sip2SdrCall(tts=...)` → `_announce()` writes to `tts_buf`.

### Changes
- `RingBufferMediaPort`: add `tts_buf: RingBuffer` parameter; read TTS first, SDR second
- `_Sip2SdrCall`: accept `tts: TtsEngine`, create `tts_buf`, pass both bufs to media port
- `_Sip2SdrAccount`: accept and forward `tts`
- `SipEngine`: accept `tts: TtsEngine`, forward to accounts
- `__main__.py`: pass `tts` to `SipEngine`

---

## PCMA Codec Support

### Design
Introduce a `Codec` enum (`PCMU`, `PCMA`) in `sip2sdr/codec.py`. Validate `audio.codec` in config loader. Replace bare `str` in `AudioConfig` with `Codec`.

PJSUA2 codec priority is set globally on the `Endpoint` after `libStart()` using strings `"PCMU/8000"` and `"PCMA/8000"` (payload types 0 and 8):
- `PCMU`: PCMU→255, PCMA→0
- `PCMA`: PCMA→255, PCMU→0

### Changes
- New file `src/sip2sdr/codec.py` with `Codec` enum
- `config.py`: `AudioConfig.codec: Codec`; validate in `load_config`
- `sip/engine.py`: `SipEngine.start()` calls `_configure_codecs()` after `libStart()`
- `config.example.yaml`: document `pcma` option
- Tests: config validation for codec field

---

## Integration Tests

Tests in `tests/test_integration.py` that run without GNU Radio or PJSUA2:

1. **Config → DTMF → retune path**: load YAML config, create `ChannelSwitchHandler` with mock retune/announce, simulate DTMF sequence, verify correct channel retuning
2. **Cancel and re-enter**: simulate `67*16#` sequence, verify only channel 16 is retuned
3. **TTS + priority buffer**: write TTS PCM to TTS buffer, verify media port returns TTS samples before SDR samples
4. **SDR fallback after TTS drains**: after TTS buffer drains, verify media port returns SDR samples
5. **Config codec validation**: valid pcmu/pcma pass; invalid raises ValueError
6. **Invalid channel DTMF**: out-of-range channel triggers "Invalid channel" announce

---

## Documentation

### `docs/setup.md`
System dependencies (gnuradio, gr-osmosdr, libhackrf-dev, espeak-ng, libpjproject-dev), venv setup, GNU Radio PYTHONPATH, dev install.

### `docs/configuration.md`
Full YAML reference: all fields, types, valid values, defaults. Includes new `pcma` codec option.

### `docs/usage.md`
Running the app, operating modes (marine/test), DTMF guide (`<digits>#` to switch, `*` to cancel), channel tables summary.

### `docs/asterisk-setup.md`
SIP account configuration for 4 extensions, TLS transport setup, SRTP, example FreePBX/Asterisk dialplan.
