"""SIP2SDR — Marine VHF Radio over SIP."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sip2sdr")
except PackageNotFoundError:
    __version__ = "0.0.0"
