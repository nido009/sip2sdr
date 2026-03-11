# SIP2SDR

Listen to Marine VHF (or LPD433) radio channels via phone — a Python application that bridges a HackRF One SDR receiver to an Asterisk PBX over SIP. Up to 4 callers can simultaneously listen to independent channels, switching channels live via DTMF tones.

**Receive-only** — no VHF transmission capability.

## Features

- **4 simultaneous SIP extensions**, each with an independent demodulator chain
- **Marine VHF** (156–162 MHz) and **LPD433** (433–434.775 MHz) operating modes
- **Live channel switching** via DTMF: dial `<channel>#` during a call
- **TTS announcements** via espeak-ng ("Channel 67", "Invalid channel")
- **PCMU or PCMA** codec, configurable globally
- **SIP-TLS + SRTP** transport — self-signed certificates accepted
- Statically typed Python 3.10+, fully tested without hardware

## Requirements

**System packages:**
```bash
sudo apt install gnuradio gr-osmosdr libhackrf-dev espeak-ng libpjproject-dev
```

**Python (in a venv):**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**GNU Radio Python path** (add to `.venv/bin/activate` or your shell profile):
```bash
export PYTHONPATH=/usr/lib/python3/dist-packages:$PYTHONPATH
```

See [`docs/setup.md`](docs/setup.md) for full installation instructions.

## Quick Start

```bash
cp config.example.yaml config.yaml
# edit config.yaml with your SIP credentials and SDR settings
python -m sip2sdr --config config.yaml
```

## Configuration

```yaml
mode: marine          # or "test" for LPD433

sdr:
  device: "hackrf"
  sample_rate: 8000000
  gain_lna: 32
  gain_vga: 30

sip:
  registrar: "sip:pbx.example.com"
  transport: tls
  srtp: required
  extensions:
    - username: "sip2sdr-1"
      password: "secret1"
      default_channel: 67

audio:
  codec: pcmu          # or "pcma"
  sample_rate: 8000
  buffer_size: 4000
```

See [`docs/configuration.md`](docs/configuration.md) for the full YAML reference.

## DTMF Controls

| Input | Action |
|-------|--------|
| `67#` | Switch to channel 67 |
| `16#` | Switch to channel 16 (distress) |
| `*`   | Cancel current input |

Valid Marine VHF channels: 1–28, 60–88. Valid LPD433 channels: 1–69.

## Documentation

- [`docs/setup.md`](docs/setup.md) — Installation and system dependencies
- [`docs/configuration.md`](docs/configuration.md) — Full YAML config reference
- [`docs/usage.md`](docs/usage.md) — Running the app and DTMF guide
- [`docs/asterisk-setup.md`](docs/asterisk-setup.md) — Asterisk PBX configuration

## Architecture

```
HackRF One (wideband IQ)
    │
    ├── DemodChain 1 (FreqXlat → NFM → 8kHz) → RingBuffer ─┐
    ├── DemodChain 2                           → RingBuffer ─┤
    ├── DemodChain 3                           → RingBuffer ─┤
    └── DemodChain 4                           → RingBuffer ─┤
                                                              │
                         PJSUA2 SIP Engine ──────────────────┘
                         ├── Extension 1 (TLS+SRTP)
                         ├── Extension 2
                         ├── Extension 3
                         └── Extension 4
                              │
                         DTMF → Channel Switch → retune()
                         TTS  → priority buffer → caller
```

## Development

```bash
# Run tests
pytest tests/ -v

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

Tests run without GNU Radio or a HackRF attached. Hardware-dependent tests skip automatically.

## License

MIT
