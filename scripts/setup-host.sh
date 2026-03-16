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
