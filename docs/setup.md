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
