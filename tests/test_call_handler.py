"""Tests for DTMF-based channel switching call handler."""

from unittest.mock import MagicMock

from sip2sdr.channels import ChannelMode
from sip2sdr.sip.call_handler import ChannelSwitchHandler, DtmfCollector


class TestDtmfCollector:
    def test_digits_accumulate(self) -> None:
        c = DtmfCollector()
        c.push("6")
        c.push("7")
        assert c.pending == "67"

    def test_hash_resets_and_returns_number(self) -> None:
        c = DtmfCollector()
        c.push("1")
        c.push("6")
        result = c.push("#")
        assert result == 16
        assert c.pending == ""

    def test_asterisk_clears_pending(self) -> None:
        c = DtmfCollector()
        c.push("6")
        c.push("7")
        result = c.push("*")
        assert result is None
        assert c.pending == ""

    def test_non_digit_ignored(self) -> None:
        c = DtmfCollector()
        c.push("A")
        assert c.pending == ""

    def test_push_returns_none_while_accumulating(self) -> None:
        c = DtmfCollector()
        assert c.push("6") is None
        assert c.push("7") is None


class TestChannelSwitchHandler:
    def test_valid_channel_calls_retune(self) -> None:
        retune_fn = MagicMock()
        announce_fn = MagicMock()
        handler = ChannelSwitchHandler(
            mode=ChannelMode.MARINE,
            retune_fn=retune_fn,
            announce_fn=announce_fn,
        )
        handler.on_dtmf("6")
        handler.on_dtmf("7")
        handler.on_dtmf("#")
        retune_fn.assert_called_once_with(67)
        announce_fn.assert_called_once_with("Channel 67")

    def test_invalid_channel_calls_invalid_announce(self) -> None:
        retune_fn = MagicMock()
        announce_fn = MagicMock()
        handler = ChannelSwitchHandler(
            mode=ChannelMode.MARINE,
            retune_fn=retune_fn,
            announce_fn=announce_fn,
        )
        handler.on_dtmf("9")
        handler.on_dtmf("9")
        handler.on_dtmf("#")
        retune_fn.assert_not_called()
        announce_fn.assert_called_once_with("Invalid channel")

    def test_star_clears_buffer(self) -> None:
        retune_fn = MagicMock()
        announce_fn = MagicMock()
        handler = ChannelSwitchHandler(
            mode=ChannelMode.MARINE,
            retune_fn=retune_fn,
            announce_fn=announce_fn,
        )
        handler.on_dtmf("9")
        handler.on_dtmf("*")
        handler.on_dtmf("1")
        handler.on_dtmf("6")
        handler.on_dtmf("#")
        retune_fn.assert_called_once_with(16)
