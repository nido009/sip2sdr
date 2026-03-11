"""YAML configuration loader for SIP2SDR.

Loads and validates the application configuration from a YAML file,
returning strongly-typed dataclass instances.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from sip2sdr.channels import ChannelMode
from sip2sdr.codec import Codec


@dataclass(frozen=True)
class SdrConfig:
    """SDR hardware and capture parameters."""

    device: str
    sample_rate: int
    gain_lna: int
    gain_vga: int
    gain_amp: bool


@dataclass(frozen=True)
class ExtensionConfig:
    """SIP extension credentials and defaults."""

    username: str
    password: str
    default_channel: int


@dataclass(frozen=True)
class SipConfig:
    """SIP layer configuration."""

    registrar: str
    transport: str
    srtp: str
    verify_certs: bool
    extensions: list[ExtensionConfig]


@dataclass(frozen=True)
class AudioConfig:
    """Audio pipeline configuration."""

    codec: Codec
    sample_rate: int
    buffer_size: int


@dataclass(frozen=True)
class Config:
    """Top-level application configuration."""

    mode: ChannelMode
    sdr: SdrConfig
    sip: SipConfig
    audio: AudioConfig


def load_config(path: Path) -> Config:
    """Load and validate configuration from a YAML file at *path*.

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the mode or codec field is unrecognised.
        KeyError: if a required field is missing.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open() as fh:
        raw: dict = yaml.safe_load(fh)

    mode_str: str = raw["mode"]
    if mode_str == "marine":
        mode = ChannelMode.MARINE
    elif mode_str == "test":
        mode = ChannelMode.TEST
    else:
        raise ValueError(f"Unknown mode: {mode_str!r} (expected 'marine' or 'test')")

    sdr_raw = raw["sdr"]
    sdr = SdrConfig(
        device=sdr_raw["device"],
        sample_rate=int(sdr_raw["sample_rate"]),
        gain_lna=int(sdr_raw["gain_lna"]),
        gain_vga=int(sdr_raw["gain_vga"]),
        gain_amp=bool(sdr_raw["gain_amp"]),
    )

    sip_raw = raw["sip"]
    extensions = [
        ExtensionConfig(
            username=e["username"],
            password=e["password"],
            default_channel=int(e["default_channel"]),
        )
        for e in sip_raw["extensions"]
    ]
    sip = SipConfig(
        registrar=sip_raw["registrar"],
        transport=sip_raw["transport"],
        srtp=sip_raw["srtp"],
        verify_certs=bool(sip_raw["verify_certs"]),
        extensions=extensions,
    )

    audio_raw = raw["audio"]
    codec_str: str = audio_raw["codec"]
    if codec_str == "pcmu":
        codec = Codec.PCMU
    elif codec_str == "pcma":
        codec = Codec.PCMA
    else:
        raise ValueError(f"Unknown codec: {codec_str!r} (expected 'pcmu' or 'pcma')")
    audio = AudioConfig(
        codec=codec,
        sample_rate=int(audio_raw["sample_rate"]),
        buffer_size=int(audio_raw["buffer_size"]),
    )

    return Config(mode=mode, sdr=sdr, sip=sip, audio=audio)
