# SIP2SDR — Bare-Metal Install (no Docker)

Tested on Ubuntu 26.04, Python 3.14, pjproject 2.17-dev, HackRF One. All steps as root
(or prefix with `sudo`).

## 1. System packages

```bash
apt-get update
apt-get install -y --no-install-recommends \
    git curl build-essential pkg-config swig \
    python3-dev \
    libssl-dev libopus-dev libasound2-dev uuid-dev \
    gnuradio gr-osmosdr hackrf libhackrf-dev \
    espeak-ng
```

There is no distro package for pjsua2, so it is built from source in step 2.

Install [uv](https://docs.astral.sh/uv/) (used for the venv and all Python packages):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 2. Build pjproject + Python bindings

```bash
cd /opt
git clone https://github.com/pjsip/pjproject.git
cd pjproject
./configure --enable-shared --disable-video --with-ssl
make dep && make -j"$(nproc)"
make install && ldconfig

# Python bindings (built for the system python3)
cd pjsip-apps/src/swig/python && make
```

Use pjproject 2.15.1 or newer; 2.14.x does not compile with SWIG 4.2+.
The bindings end up in `build/lib.linux-x86_64-cpython-<ver>/` and are tied to that
Python version — rebuild them if the Python version changes.

## 3. Clone sip2sdr and create the venv

```bash
cd /opt
git clone https://github.com/nido009/sip2sdr.git
cd sip2sdr

# --system-site-packages makes the apt-installed gnuradio / osmosdr importable.
uv venv --system-site-packages --python /usr/bin/python3
# --inexact keeps files we copy into the venv by hand (pjsua2, next step).
uv sync --inexact
```

`uv sync` installs sip2sdr (editable) plus the dev group, pinned by `uv.lock`.

## 4. Install pjsua2 into the venv

```bash
SP=$(uv run python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
B=/opt/pjproject/pjsip-apps/src/swig/python/build/lib.linux-x86_64-cpython-314
cp "$B"/_pjsua2.*.so "$B"/pjsua2.py "$SP"/
```

Adjust `cpython-314` to your Python version (`ls $B/..`).

## 5. HackRF host setup

```bash
./scripts/setup-host.sh
```

Installs the udev rules, blacklists the in-kernel `hackrf` module and refreshes the
initramfs. Unplug and replug the HackRF afterwards, then check:

```bash
hackrf_info
```

## 6. Verify

```bash
uv run python -c "import pjsua2; print(pjsua2.Endpoint().libVersion().full)"
uv run python -c "import gnuradio, osmosdr"
uv run pytest
```

All tests should pass with nothing skipped.

## 7. Configure and run

```bash
cp config.example.yaml config.yaml   # gitignored; set registrar, extensions, passwords
uv run sip2sdr --help
```

## Troubleshooting

- **`cannot open shared object file: libpjsua2.so`** — run `ldconfig`.
- **Segfault in `createPort`** — the PJSUA library was not initialised
  (`Endpoint.libCreate()` + `libInit()` must run first).
- **`hackrf_info` finds nothing as non-root** — replug after `setup-host.sh`; check
  that your user is in `plugdev`.
- **Old HackRF firmware** (`hackrf_info` shows e.g. 2023.01.1) works, but upgrading with
  `hackrf_spiflash -w` is recommended.
