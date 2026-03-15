# Docker Distribution Design for SIP2SDR

**Date:** 2026-03-15
**Status:** Approved

## Goal

Package SIP2SDR as a Docker image so it can run on any Linux machine with Docker installed, without requiring users to manually install GNU Radio, PJSUA2, or other system dependencies.

## Target Audience

- Primary: technical users who can clone a repo and run `docker compose up -d`
- Stretch: non-technical users who can follow a numbered list

## Distribution Method

Build from source — users clone the repository and run `docker compose build`. No image registry required.

## New Files

```
sip2sdr/
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
└── scripts/
    └── setup-host.sh
```

## Dockerfile

Base image: `debian:bookworm-slim`

- Installs system packages in a single apt layer: `gnuradio`, `gr-osmosdr`, `python3-pjsua2`, `libpjproject-dev`, `hackrf`, `espeak-ng`, `python3`, `python3-pip`
- Sets `PYTHONPATH=/usr/lib/python3/dist-packages` for GNU Radio Python bindings
- Installs pip dependencies with `--break-system-packages` (no venv needed inside container)
- Copies `src/` and `pyproject.toml`, runs `pip install -e .`
- Entrypoint: `python3 -m sip2sdr -c /config/config.yaml`

## docker-compose.yml

```yaml
services:
  sip2sdr:
    build: .
    restart: unless-stopped
    devices:
      - /dev/bus/usb:/dev/bus/usb
    volumes:
      - ./config.yaml:/config/config.yaml:ro
    network_mode: host
```

Key decisions:
- `devices: /dev/bus/usb` — USB passthrough without full privileged mode
- `network_mode: host` — SIP/RTP require the host network stack; avoids complex RTP port range mapping
- Config mounted read-only at `/config/config.yaml`
- `restart: unless-stopped` — survives reboots

## scripts/setup-host.sh

One-time script run as root on the host before first launch. Installs HackRF udev rules and reloads udev so the device is accessible to the Docker `--device` passthrough without requiring `privileged: true`.

## User Workflow

```bash
# One-time setup
git clone <repo> sip2sdr && cd sip2sdr
sudo bash scripts/setup-host.sh
cp config.example.yaml config.yaml
nano config.yaml

# Start
docker compose build
docker compose up -d

# Logs
docker compose logs -f

# Update
git pull && docker compose build && docker compose up -d
```

## What Is Not Changing

- Application source code — no changes
- Configuration format — `config.yaml` schema unchanged
- No image registry required
