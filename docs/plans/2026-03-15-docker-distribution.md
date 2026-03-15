# Docker Distribution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `Dockerfile`, `docker-compose.yml`, `.dockerignore`, and `scripts/setup-host.sh` so SIP2SDR can be built and run on any Linux machine with Docker, with HackRF One passed through via USB device mapping.

**Architecture:** Single `debian:bookworm-slim` image installs all system deps (gnuradio, gr-osmosdr, python3-pjsua2, espeak-ng, hackrf) and the app. `docker-compose.yml` handles USB passthrough, config volume mount, host networking, and auto-restart. A one-time `setup-host.sh` installs HackRF udev rules on the host.

**Tech Stack:** Docker, docker-compose v2, debian:bookworm-slim, GNU Radio, PJSUA2, HackRF

---

### Task 1: `.dockerignore`

**Files:**
- Create: `.dockerignore`

No tests needed — this is a config file. Verify by inspecting the build context output.

**Step 1: Create `.dockerignore`**

```
.venv/
.worktrees/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/
dist/
build/
docs/
tests/
.git/
*.md
config.yaml
```

**Step 2: Commit**

```bash
git add .dockerignore
git commit -m "chore: add .dockerignore for Docker build context"
```

---

### Task 2: `Dockerfile`

**Files:**
- Create: `Dockerfile`

No unit tests for Dockerfiles — verification is `docker build` in Task 5.

**Step 1: Create `Dockerfile`**

```dockerfile
FROM debian:bookworm-slim

# Install all system dependencies in a single layer to keep image lean
RUN apt-get update && apt-get install -y --no-install-recommends \
    gnuradio \
    gr-osmosdr \
    python3-pjsua2 \
    libpjproject-dev \
    hackrf \
    espeak-ng \
    python3 \
    python3-pip \
 && rm -rf /var/lib/apt/lists/*

# GNU Radio Python bindings are installed into system site-packages, not pip-installable
ENV PYTHONPATH=/usr/lib/python3/dist-packages

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/

# Install app pip deps into the system Python (container is the isolation boundary)
RUN pip install --break-system-packages -e .

# Config is provided at runtime via volume mount
CMD ["python3", "-m", "sip2sdr", "-c", "/config/config.yaml"]
```

**Step 2: Commit**

```bash
git add Dockerfile
git commit -m "feat: add Dockerfile based on debian:bookworm-slim"
```

---

### Task 3: `docker-compose.yml`

**Files:**
- Create: `docker-compose.yml`

**Step 1: Create `docker-compose.yml`**

```yaml
services:
  sip2sdr:
    build: .
    restart: unless-stopped
    devices:
      - /dev/bus/usb:/dev/bus/usb   # HackRF One USB passthrough
    volumes:
      - ./config.yaml:/config/config.yaml:ro
    network_mode: host              # SIP/RTP need host network stack
```

Notes:
- `devices: /dev/bus/usb` — passes all USB devices without requiring `privileged: true`
- `network_mode: host` — avoids complex RTP port range mapping; SIP NAT traversal relies on the actual host IP
- Config is read-only to prevent accidental modification by the container

**Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add docker-compose.yml with USB and host network config"
```

---

### Task 4: `scripts/setup-host.sh`

**Files:**
- Create: `scripts/setup-host.sh`

This script is run once on the host (as root) before the first `docker compose up`. It installs HackRF udev rules so the USB device is accessible to the Docker device passthrough without privileged mode.

**Step 1: Create `scripts/setup-host.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Error: run as root (sudo bash scripts/setup-host.sh)" >&2
    exit 1
fi

echo "Installing HackRF udev rules..."

# Install hackrf package if not present (provides udev rules)
if ! command -v hackrf_info &>/dev/null; then
    apt-get update -q
    apt-get install -y --no-install-recommends hackrf
fi

# Copy udev rules if not already in place
RULES_SRC=/usr/lib/udev/rules.d/53-hackrf.rules
RULES_DST=/etc/udev/rules.d/53-hackrf.rules

if [[ ! -f "$RULES_DST" ]]; then
    cp "$RULES_SRC" "$RULES_DST"
    echo "Copied $RULES_SRC -> $RULES_DST"
else
    echo "udev rules already in place: $RULES_DST"
fi

udevadm control --reload-rules
udevadm trigger

echo ""
echo "Done. If your HackRF is already plugged in, unplug and replug it now."
```

**Step 2: Make executable and commit**

```bash
chmod +x scripts/setup-host.sh
git add scripts/setup-host.sh
git commit -m "feat: add setup-host.sh for HackRF udev rules"
```

---

### Task 5: Verify Docker build

No hardware required for this step — just verify the image builds cleanly.

**Step 1: Build the image**

```bash
docker compose build
```

Expected: build completes without errors. Watch for:
- `apt-get` failures (package name changes) — `gr-osmosdr` may be `gnuradio-osmosdr` on some versions
- pip install errors

If `gr-osmosdr` is not found, try `gnuradio-osmosdr` in the Dockerfile.

**Step 2: Verify the image exists**

```bash
docker images | grep sip2sdr
```

Expected: one line with image name and a recent timestamp.

**Step 3: Smoke-test the container (no config)**

```bash
docker compose run --rm sip2sdr python3 -c "
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import sip2sdr
print('sip2sdr OK:', sip2sdr.__file__)
try:
    import gnuradio
    print('gnuradio OK:', gnuradio.__version__)
except ImportError as e:
    print('gnuradio missing:', e)
try:
    import pjsua2
    print('pjsua2 OK')
except ImportError as e:
    print('pjsua2 missing:', e)
"
```

Expected: `sip2sdr OK`, `gnuradio OK`, `pjsua2 OK` all printed.

**Step 4: Commit any Dockerfile fixes found during build**

```bash
git add Dockerfile
git commit -m "fix: correct apt package names in Dockerfile"
```

(Only needed if package names needed adjustment.)

---

### Task 6: Update `docs/setup.md` with Docker section

**Files:**
- Modify: `docs/setup.md`

**Step 1: Add Docker section to `docs/setup.md`**

Append the following section after the existing content:

```markdown
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
```

**Step 2: Commit**

```bash
git add docs/setup.md
git commit -m "docs: add Docker setup section to setup.md"
```

---

### Task 7: Push to GitLab

```bash
git push
```

Expected: all commits from Tasks 1–6 pushed to `main` on `gitlab.addix.net`.
