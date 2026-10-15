# SIP2SDR — Usage Guide

## Starting the Application

```bash
# GNU Radio comes from apt: the venv must be created with --system-site-packages
# (see setup.md), otherwise export PYTHONPATH=/usr/lib/python3/dist-packages.
uv run sip2sdr --config config.yaml
# or
uv run python -m sip2sdr --config config.yaml
```

### Command-Line Options

```
usage: sip2sdr [-h] --config CONFIG [--log-level LOG_LEVEL]

options:
  --config CONFIG        Path to YAML config file
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
