# SIP2SDR — Installation & Setup

## System Requirements

- Linux (Debian/Ubuntu recommended) or macOS (for development)
- Python 3.10+
- [HackRF One](https://greatscottgadgets.com/hackrf/) SDR hardware

> Installing without Docker? Follow the full step-by-step guide in [bare-metal.md](bare-metal.md).

## System Package Dependencies

Install the following system packages before creating the Python venv:

```bash
# Debian/Ubuntu
sudo apt install \
    gnuradio gr-osmosdr \
    libhackrf-dev hackrf \
    espeak-ng
# pjsua2 has no distro package — build it from source, see docs/bare-metal.md

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

## Docker (Recommended for Production)

Docker packages all system dependencies (GNU Radio, PJSUA2, espeak-ng) into a
self-contained image. No system packages need to be installed manually.

### Requirements

- Linux host with Docker and docker-compose v2 installed
- HackRF One connected via USB

### One-Time Host Setup

Install HackRF udev rules so the device is accessible inside the container:

```bash
sudo bash scripts/setup-host.sh
```

Unplug and replug the HackRF if it was already connected.

### Configure

```bash
cp config.example.yaml config.yaml
nano config.yaml   # fill in SIP credentials, SDR parameters
```

### Build and Start

```bash
docker compose build
docker compose up -d
```

The container restarts automatically on reboot.

### Logs

```bash
docker compose logs -f
```

### Update

```bash
git pull
docker compose build
docker compose up -d
```
