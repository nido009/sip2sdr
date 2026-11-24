#!/usr/bin/env bash
# Checks whether the HackRF has a working receive antenna.
# Exit code: 0 antenna present, 1 no antenna, 2 measurement failed.
set -uo pipefail

SERVICE=${SERVICE:-sip2sdr}
SIGNAL_BAND=${SIGNAL_BAND:-87:108}      # MHz, FM broadcast
CONTROL_BAND=${CONTROL_BAND:-400:420}   # MHz, normally quiet
LNA=${LNA:-16}                          # low gains, so strong stations do not overload
VGA=${VGA:-20}
SWEEPS=${SWEEPS:-20}
MIN_SNR_DB=${MIN_SNR_DB:-20}            # peak above noise floor that counts as "antenna"

command -v hackrf_sweep >/dev/null || { echo "hackrf_sweep not installed" >&2; exit 2; }

restart=0
cleanup() {
    if [ "$restart" = 1 ]; then
        systemctl start "$SERVICE"
        sleep 3
        echo "$SERVICE: $(systemctl is-active "$SERVICE")"
    fi
}
trap cleanup EXIT

if systemctl is-active --quiet "$SERVICE"; then
    echo "stopping $SERVICE for the measurement"
    systemctl stop "$SERVICE" || exit 2
    restart=1
    sleep 2
fi

measure() {
    timeout 30 hackrf_sweep -f "$1" -l "$LNA" -g "$VGA" -a 0 -w 100000 -N "$SWEEPS" 2>/dev/null |
        awk -F', ' '{ for (i = 7; i <= NF; i++) { f = $3 + (i - 6.5) * $5; sum[f] += $i; n[f]++ } }
                    END { for (f in sum) printf "%.1f %.2f\n", sum[f] / n[f], f / 1e6 }' |
        sort -n |
        awk '{ db[NR] = $1; mhz[NR] = $2 }
             END { if (NR < 10) exit 1
                   printf "%.1f %.1f %.2f\n", db[int((NR + 1) / 2)], db[NR], mhz[NR] }'
}

read -r floor peak peak_mhz < <(measure "$SIGNAL_BAND") || true
read -r cfloor cpeak cpeak_mhz < <(measure "$CONTROL_BAND") || true
if [ -z "${peak:-}" ] || [ -z "${cpeak:-}" ]; then
    echo "measurement failed: no data from hackrf_sweep (device missing or busy?)" >&2
    exit 2
fi

snr=$(awk -v p="$peak" -v f="$floor" 'BEGIN { printf "%.0f", p - f }')
csnr=$(awk -v p="$cpeak" -v f="$cfloor" 'BEGIN { printf "%.0f", p - f }')

echo "signal band  $SIGNAL_BAND MHz: floor $floor dB, peak $peak dB at $peak_mhz MHz, $snr dB above floor"
echo "control band $CONTROL_BAND MHz: floor $cfloor dB, peak $cpeak dB at $cpeak_mhz MHz, $csnr dB above floor"

if [ "$snr" -ge "$MIN_SNR_DB" ] && [ "$csnr" -lt "$MIN_SNR_DB" ]; then
    echo "RESULT: antenna present"
    exit 0
elif [ "$snr" -ge "$MIN_SNR_DB" ]; then
    echo "RESULT: unclear, the control band is not quiet (pick another CONTROL_BAND)"
    exit 2
else
    echo "RESULT: no antenna (or one that does not receive $SIGNAL_BAND MHz)"
    exit 1
fi
