"""Shared pytest fixtures for SIP2SDR tests."""

import pytest


@pytest.fixture
def marine_config_dict() -> dict[str, object]:
    """Minimal valid marine mode config dict."""
    return {
        "mode": "marine",
        "sdr": {
            "device": "hackrf",
            "sample_rate": 8_000_000,
            "gain_lna": 32,
            "gain_vga": 30,
            "gain_amp": False,
        },
        "sip": {
            "registrar": "sip:pbx.example.com",
            "transport": "tls",
            "srtp": "required",
            "verify_certs": False,
            "extensions": [
                {"username": "sip2sdr-1", "password": "secret1", "default_channel": 67}
            ],
        },
        "audio": {
            "codec": "pcmu",
            "sample_rate": 8000,
            "buffer_size": 4000,
        },
    }


@pytest.fixture
def test_config_dict() -> dict[str, object]:
    """Minimal valid test/LPD mode config dict."""
    return {
        "mode": "test",
        "sdr": {
            "device": "hackrf",
            "sample_rate": 2_000_000,
            "gain_lna": 32,
            "gain_vga": 30,
            "gain_amp": False,
        },
        "sip": {
            "registrar": "sip:pbx.example.com",
            "transport": "tls",
            "srtp": "required",
            "verify_certs": False,
            "extensions": [
                {"username": "sip2sdr-1", "password": "secret1", "default_channel": 1}
            ],
        },
        "audio": {
            "codec": "pcmu",
            "sample_rate": 8000,
            "buffer_size": 4000,
        },
    }
