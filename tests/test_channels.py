"""Tests for Marine VHF and LPD433 channel tables."""

import pytest

from sip2sdr.channels import (
    ChannelMode,
    get_channel_frequency,
    get_channel_table,
    is_valid_channel,
)


class TestMarineVHF:
    def test_channel_16_is_distress(self) -> None:
        assert get_channel_frequency(16, ChannelMode.MARINE) == 156.800

    def test_channel_67_is_kieler_foerde(self) -> None:
        assert get_channel_frequency(67, ChannelMode.MARINE) == 156.375

    def test_channel_1_frequency(self) -> None:
        assert get_channel_frequency(1, ChannelMode.MARINE) == 156.050

    def test_channel_88_is_valid(self) -> None:
        assert is_valid_channel(88, ChannelMode.MARINE) is True

    def test_channel_0_is_invalid(self) -> None:
        assert is_valid_channel(0, ChannelMode.MARINE) is False

    def test_channel_89_is_invalid(self) -> None:
        assert is_valid_channel(89, ChannelMode.MARINE) is False

    def test_channel_table_has_expected_keys(self) -> None:
        table = get_channel_table(ChannelMode.MARINE)
        assert 16 in table
        assert 67 in table
        assert 70 in table  # DSC

    def test_invalid_channel_raises(self) -> None:
        with pytest.raises(KeyError):
            get_channel_frequency(99, ChannelMode.MARINE)


class TestLPD433:
    def test_channel_1_frequency(self) -> None:
        assert get_channel_frequency(1, ChannelMode.TEST) == pytest.approx(433.075, abs=1e-3)

    def test_channel_69_frequency(self) -> None:
        assert get_channel_frequency(69, ChannelMode.TEST) == pytest.approx(434.775, abs=1e-3)

    def test_channel_2_is_25khz_above_1(self) -> None:
        f1 = get_channel_frequency(1, ChannelMode.TEST)
        f2 = get_channel_frequency(2, ChannelMode.TEST)
        assert f2 - f1 == pytest.approx(0.025, abs=1e-6)

    def test_channel_0_is_invalid(self) -> None:
        assert is_valid_channel(0, ChannelMode.TEST) is False

    def test_channel_70_is_invalid(self) -> None:
        assert is_valid_channel(70, ChannelMode.TEST) is False

    def test_channel_table_has_69_channels(self) -> None:
        table = get_channel_table(ChannelMode.TEST)
        assert len(table) == 69
