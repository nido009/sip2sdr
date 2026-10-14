# SIP2SDR — Bare-Metal Install (no Docker)

Tested on Ubuntu 26.04, Python 3.14, pjproject 2.17-dev, HackRF One. All steps as root
(or prefix with `sudo`).

## 1. System packages

```bash
apt-get update
apt-get install -y --no-install-recommends \
    git build-essential pkg-config swig \
    python3-dev python3-venv \
    libssl-dev libopus-dev libasound2-dev uuid-dev \
    gnuradio gr-osmosdr hackrf libhackrf-dev \
    espeak-ng
```

There is no distro package for pjsua2, so it is built from source in step 2.

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
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e '.[dev]'
```

## 4. Install pjsua2 into the venv

```bash
SP=$(.venv/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
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
.venv/bin/python -c "import pjsua2; print(pjsua2.Endpoint().libVersion().full)"
.venv/bin/python -c "import gnuradio, osmosdr"
.venv/bin/pytest
```

All tests should pass with nothing skipped.

## 7. Configure and run

```bash
cp config.example.yaml config.yaml   # gitignored; set registrar, extensions, passwords
.venv/bin/sip2sdr --help
```

## Troubleshooting

- **`cannot open shared object file: libpjsua2.so`** — run `ldconfig`.
- **Segfault in `createPort`** — the PJSUA library was not initialised
  (`Endpoint.libCreate()` + `libInit()` must run first).
- **`hackrf_info` finds nothing as non-root** — replug after `setup-host.sh`; check
  that your user is in `plugdev`.
- **Old HackRF firmware** (`hackrf_info` shows e.g. 2023.01.1) works, but upgrading with
  `hackrf_spiflash -w` is recommended.
