"""Tests for YAML configuration loader."""

from pathlib import Path

import pytest
import yaml

from sip2sdr.channels import ChannelMode
from sip2sdr.config import Config, ExtensionConfig, load_config


class TestLoadConfig:
    def test_load_from_file(self, tmp_path: Path, marine_config_dict: dict) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(marine_config_dict))
        cfg = load_config(cfg_file)
        assert isinstance(cfg, Config)

    def test_marine_mode_parsed(self, tmp_path: Path, marine_config_dict: dict) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(marine_config_dict))
        cfg = load_config(cfg_file)
        assert cfg.mode == ChannelMode.MARINE

    def test_test_mode_parsed(self, tmp_path: Path, test_config_dict: dict) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(test_config_dict))
        cfg = load_config(cfg_file)
        assert cfg.mode == ChannelMode.TEST

    def test_sdr_fields(self, tmp_path: Path, marine_config_dict: dict) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(marine_config_dict))
        cfg = load_config(cfg_file)
        assert cfg.sdr.sample_rate == 8_000_000
        assert cfg.sdr.gain_lna == 32
        assert cfg.sdr.gain_vga == 30
        assert cfg.sdr.gain_amp is False

    def test_extensions_parsed(self, tmp_path: Path, marine_config_dict: dict) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(marine_config_dict))
        cfg = load_config(cfg_file)
        assert len(cfg.sip.extensions) == 1
        ext = cfg.sip.extensions[0]
        assert isinstance(ext, ExtensionConfig)
        assert ext.username == "sip2sdr-1"
        assert ext.default_channel == 67

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_invalid_mode_raises(self, tmp_path: Path, marine_config_dict: dict) -> None:
        marine_config_dict["mode"] = "invalid"
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(marine_config_dict))
        with pytest.raises(ValueError, match="Unknown mode"):
            load_config(cfg_file)

    def test_audio_fields(self, tmp_path: Path, marine_config_dict: dict) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(marine_config_dict))
        cfg = load_config(cfg_file)
        assert cfg.audio.sample_rate == 8000
        assert cfg.audio.buffer_size == 4000
