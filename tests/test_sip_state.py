"""Tests for SIP layer observable state (DTMF history, call tracking)."""

from unittest.mock import MagicMock

from sip2sdr.channels import ChannelMode
from sip2sdr.sip.call_handler import ChannelSwitchHandler


class TestChannelSwitchHandlerDtmfEvents:
    def test_dtmf_event_fn_called_for_each_digit(self) -> None:
        dtmf_event_fn = MagicMock()
        handler = ChannelSwitchHandler(
            mode=ChannelMode.MARINE,
            retune_fn=MagicMock(),
            announce_fn=MagicMock(),
            dtmf_event_fn=dtmf_event_fn,
        )
        handler.on_dtmf("6")
        handler.on_dtmf("7")
        handler.on_dtmf("#")
        assert dtmf_event_fn.call_count == 3
        calls = [c.args[0] for c in dtmf_event_fn.call_args_list]
        assert calls == ["6", "7", "#"]

    def test_dtmf_event_fn_not_required(self) -> None:
        """ChannelSwitchHandler without dtmf_event_fn does not raise."""
        handler = ChannelSwitchHandler(
            mode=ChannelMode.MARINE,
            retune_fn=MagicMock(),
            announce_fn=MagicMock(),
        )
        handler.on_dtmf("6")
        handler.on_dtmf("7")
        handler.on_dtmf("#")  # should not raise

    def test_channel_switch_fn_called_on_valid_channel(self) -> None:
        channel_switch_fn = MagicMock()
        handler = ChannelSwitchHandler(
            mode=ChannelMode.MARINE,
            retune_fn=MagicMock(),
            announce_fn=MagicMock(),
            channel_switch_fn=channel_switch_fn,
        )
        handler.on_dtmf("6")
        handler.on_dtmf("7")
        handler.on_dtmf("#")
        channel_switch_fn.assert_called_once_with(67)

    def test_channel_switch_fn_not_called_on_invalid(self) -> None:
        channel_switch_fn = MagicMock()
        handler = ChannelSwitchHandler(
            mode=ChannelMode.MARINE,
            retune_fn=MagicMock(),
            announce_fn=MagicMock(),
            channel_switch_fn=channel_switch_fn,
        )
        handler.on_dtmf("9")
        handler.on_dtmf("9")
        handler.on_dtmf("#")
        channel_switch_fn.assert_not_called()
