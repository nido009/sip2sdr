# SIP2SDR — Installation & Setup

## System Requirements

- Linux (Debian/Ubuntu recommended) or macOS (for development)
- Python 3.10+
- [HackRF One](https://greatscottgadgets.com/hackrf/) SDR hardware

> Installing without Docker? Follow the full step-by-step guide in [bare-metal.md](bare-metal.md).

## System Package Dependencies

Install the following system packages before creating the Python environment:

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

## Python Environment (uv)

The project uses [uv](https://docs.astral.sh/uv/) (install: `curl -LsSf https://astral.sh/uv/install.sh | sh`
or `brew install uv`). All Python packages live in the project `.venv`; do **not** install pip packages system-wide.

```bash
cd /path/to/sip2sdr
uv venv --system-site-packages   # lets the venv see apt-installed gnuradio / osmosdr
uv sync --inexact                # runtime + dev deps from uv.lock; keeps pjsua2 copied into the venv
```

On macOS (no system GNU Radio) a plain `uv sync` is enough.

## GNU Radio Python Bindings

GNU Radio installs its Python bindings into the system site-packages, not into the venv. The
`--system-site-packages` venv above makes them importable. Without it, export the path before
running the application or tests:

```bash
export PYTHONPATH=/usr/lib/python3/dist-packages:$PYTHONPATH
```

## Verify Installation

```bash
uv run python -c "import sip2sdr; print(sip2sdr.__version__)"
# → 0.1.0

espeak-ng --version
# → eSpeak NG text-to-speech: 1.xx ...

# If GNU Radio is installed:
uv run python -c "import gnuradio; print(gnuradio.__version__)"
```

## Running Tests

```bash
uv run pytest tests/ -v
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
