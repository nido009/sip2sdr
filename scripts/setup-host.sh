#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Error: run as root (sudo bash scripts/setup-host.sh)" >&2
    exit 1
fi

RULES_DST=/etc/udev/rules.d/53-hackrf.rules
BLACKLIST_DST=/etc/modprobe.d/blacklist-hackrf.conf

echo "Installing HackRF udev rules..."

# Install hackrf package if not present (provides hackrf_info and usually the udev rules)
if ! command -v hackrf_info &>/dev/null; then
    apt-get update -q
    apt-get install -y --no-install-recommends hackrf
fi

# The rules file location differs between distros/packages, so ask dpkg instead of guessing.
RULES_SRC=""
for pkg in hackrf libhackrf0 libhackrf-dev; do
    RULES_SRC=$(dpkg -L "$pkg" 2>/dev/null | grep -m1 '53-hackrf\.rules$' || true)
    [[ -n "$RULES_SRC" && -f "$RULES_SRC" ]] && break
    RULES_SRC=""
done

if [[ -f "$RULES_DST" ]]; then
    echo "udev rules already in place: $RULES_DST"
elif [[ -n "$RULES_SRC" ]]; then
    cp "$RULES_SRC" "$RULES_DST"
    echo "Copied $RULES_SRC -> $RULES_DST"
else
    echo "No packaged udev rules found; writing $RULES_DST"
    getent group plugdev >/dev/null || groupadd plugdev
    cat > "$RULES_DST" <<'EOF'
# HackRF One
ATTR{idVendor}=="1d50", ATTR{idProduct}=="6089", SYMLINK+="hackrf-one-%k", MODE="660", GROUP="plugdev", TAG+="uaccess"
# HackRF Jawbreaker
ATTR{idVendor}=="1d50", ATTR{idProduct}=="604b", SYMLINK+="hackrf-jawbreaker-%k", MODE="660", GROUP="plugdev", TAG+="uaccess"
# rad1o
ATTR{idVendor}=="1d50", ATTR{idProduct}=="cc15", SYMLINK+="rad1o-%k", MODE="660", GROUP="plugdev", TAG+="uaccess"
EOF
fi

# The in-kernel V4L2 "hackrf" driver claims the device and blocks libhackrf/gr-osmosdr.
if [[ ! -f "$BLACKLIST_DST" ]]; then
    echo "blacklist hackrf" > "$BLACKLIST_DST"
    echo "Wrote $BLACKLIST_DST"
fi
if lsmod | grep -q '^hackrf '; then
    rmmod hackrf || echo "Could not unload kernel hackrf module; reboot to apply the blacklist."
fi
command -v update-initramfs &>/dev/null && update-initramfs -u

udevadm control --reload-rules
udevadm trigger

echo ""
echo "Done. If your HackRF is already plugged in, unplug and replug it now."
echo "Verify with: hackrf_info"
