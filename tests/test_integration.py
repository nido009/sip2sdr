"""Integration tests for the SIP2SDR pipeline (no hardware required).

These tests exercise multi-component paths using only pure-Python modules:
channels, config, ring_buffer, tts, call_handler, and the media port
priority logic.  GNU Radio and PJSUA2 are not required.
"""

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import yaml

from sip2sdr.audio.ring_buffer import RingBuffer
from sip2sdr.channels import ChannelMode, get_channel_frequency
from sip2sdr.codec import Codec
from sip2sdr.config import load_config
from sip2sdr.sip.call_handler import ChannelSwitchHandler
from sip2sdr.sip.media_port import _read_frame


class TestDtmfToRetunePath:
    """Full DTMF→retune path using only pure-Python components."""

    def _make_handler(self) -> tuple[ChannelSwitchHandler, MagicMock, MagicMock]:
        retune_fn = MagicMock()
        announce_fn = MagicMock()
        handler = ChannelSwitchHandler(
            mode=ChannelMode.MARINE,
            retune_fn=retune_fn,
            announce_fn=announce_fn,
        )
        return handler, retune_fn, announce_fn

    def test_simple_channel_switch(self) -> None:
        handler, retune_fn, announce_fn = self._make_handler()
        for digit in "16#":
            handler.on_dtmf(digit)
        retune_fn.assert_called_once_with(16)
        announce_fn.assert_called_once_with("Channel 16")

    def test_cancel_and_reenter(self) -> None:
        """Pressing * mid-sequence clears the buffer; only the final channel is applied."""
        handler, retune_fn, announce_fn = self._make_handler()
        for digit in "67*16#":
            handler.on_dtmf(digit)
        retune_fn.assert_called_once_with(16)

    def test_invalid_channel_no_retune(self) -> None:
        handler, retune_fn, announce_fn = self._make_handler()
        for digit in "99#":
            handler.on_dtmf(digit)
        retune_fn.assert_not_called()
        announce_fn.assert_called_once_with("Invalid channel")

    def test_multiple_switches_in_sequence(self) -> None:
        handler, retune_fn, announce_fn = self._make_handler()
        for digit in "16#67#":
            handler.on_dtmf(digit)
        assert retune_fn.call_count == 2
        retune_fn.assert_any_call(16)
        retune_fn.assert_any_call(67)

    def test_channel_frequency_matches_table(self) -> None:
        """Verify the channel the handler accepts maps to the expected frequency."""
        handler, retune_fn, _ = self._make_handler()
        for digit in "16#":
            handler.on_dtmf(digit)
        channel = retune_fn.call_args[0][0]
        freq = get_channel_frequency(channel, ChannelMode.MARINE)
        assert freq == pytest.approx(156.800, abs=1e-3)


class TestTtsPriorityIntegration:
    """TTS priority buffer interacts correctly with SDR buffer via _read_frame."""

    def test_tts_heard_before_sdr(self) -> None:
        sdr = RingBuffer(4000)
        tts = RingBuffer(4000)
        sdr.write(np.full(160, 1, dtype=np.int16))
        tts.write(np.full(160, 2, dtype=np.int16))
        frame = _read_frame(sdr, tts, 160)
        assert frame[0] == 2

    def test_sdr_resumes_after_tts_drains(self) -> None:
        sdr = RingBuffer(4000)
        tts = RingBuffer(4000)
        sdr.write(np.full(320, 5, dtype=np.int16))
        tts.write(np.full(160, 9, dtype=np.int16))
        first = _read_frame(sdr, tts, 160)
        second = _read_frame(sdr, tts, 160)
        assert first[0] == 9   # TTS
        assert second[0] == 5  # SDR resumed


class TestConfigIntegration:
    """Config loading integrates correctly with codec and mode validation."""

    def _write_config(self, tmp_path: Path, audio_overrides: dict | None = None) -> Path:
        base: dict = {
            "mode": "marine",
            "sdr": {"device": "hackrf", "sample_rate": 8_000_000,
                    "gain_lna": 32, "gain_vga": 30, "gain_amp": False},
            "sip": {"registrar": "sip:pbx.example.com", "transport": "tls",
                    "srtp": "required", "verify_certs": False,
                    "extensions": [{"username": "u", "password": "p", "default_channel": 67}]},
            "audio": {"codec": "pcmu", "sample_rate": 8000, "buffer_size": 4000},
        }
        if audio_overrides:
            base["audio"].update(audio_overrides)  # type: ignore[union-attr]
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(base))
        return cfg_file

    def test_pcmu_config_loads(self, tmp_path: Path) -> None:
        cfg = load_config(self._write_config(tmp_path))
        assert cfg.audio.codec == Codec.PCMU

    def test_pcma_config_loads(self, tmp_path: Path) -> None:
        cfg = load_config(self._write_config(tmp_path, {"codec": "pcma"}))
        assert cfg.audio.codec == Codec.PCMA

    def test_invalid_codec_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unknown codec"):
            load_config(self._write_config(tmp_path, {"codec": "g722"}))

    def test_test_mode_lpd_channels_valid(self, tmp_path: Path) -> None:
        from sip2sdr.channels import is_valid_channel
        base: dict = {
            "mode": "test",
            "sdr": {"device": "hackrf", "sample_rate": 2_000_000,
                    "gain_lna": 32, "gain_vga": 30, "gain_amp": False},
            "sip": {"registrar": "sip:pbx.example.com", "transport": "tls",
                    "srtp": "required", "verify_certs": False,
                    "extensions": [{"username": "u", "password": "p", "default_channel": 1}]},
            "audio": {"codec": "pcmu", "sample_rate": 8000, "buffer_size": 4000},
        }
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(base))
        cfg = load_config(cfg_file)
        assert is_valid_channel(cfg.sip.extensions[0].default_channel, cfg.mode)
