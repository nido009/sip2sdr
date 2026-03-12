"""Incoming call and DTMF channel-switch logic.

``DtmfCollector`` accumulates DTMF digits until a ``#`` terminator is
received, then returns the parsed channel number.

``ChannelSwitchHandler`` orchestrates validation and retuning, and
optionally notifies observers of each raw DTMF digit and successful
channel switches.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from sip2sdr.channels import ChannelMode, is_valid_channel

logger = logging.getLogger(__name__)


class DtmfCollector:
    """Accumulate DTMF digits and parse on ``#``.

    Digits are buffered until a ``#`` is received, at which point the
    accumulated string is parsed as a decimal integer and returned.
    Pressing ``*`` clears the buffer without returning a value.
    """

    def __init__(self) -> None:
        self._digits: list[str] = []

    @property
    def pending(self) -> str:
        """Currently buffered digit string."""
        return "".join(self._digits)

    def push(self, digit: str) -> int | None:
        """Process one DTMF digit.

        Args:
            digit: Single character: ``0``-``9``, ``*``, or ``#``.

        Returns:
            Parsed integer channel number when ``#`` is received,
            ``None`` otherwise.
        """
        if digit == "#":
            number_str = "".join(self._digits)
            self._digits.clear()
            if number_str.isdigit():
                return int(number_str)
            return None
        if digit == "*":
            self._digits.clear()
            return None
        if digit.isdigit():
            self._digits.append(digit)
        return None


class ChannelSwitchHandler:
    """Handle DTMF-driven channel switching for a single SIP call.

    Args:
        mode: Operating mode (determines valid channel range).
        retune_fn: Callable invoked with the new channel number when valid.
        announce_fn: Callable invoked with an announcement text string.
        dtmf_event_fn: Optional callback invoked with every raw DTMF digit
            received (for observability / history tracking).
        channel_switch_fn: Optional callback invoked with the new channel
            number after a successful channel switch.
    """

    def __init__(
        self,
        mode: ChannelMode,
        retune_fn: Callable[[int], None],
        announce_fn: Callable[[str], None],
        dtmf_event_fn: Callable[[str], None] | None = None,
        channel_switch_fn: Callable[[int], None] | None = None,
    ) -> None:
        self._mode = mode
        self._retune = retune_fn
        self._announce = announce_fn
        self._dtmf_event_fn = dtmf_event_fn
        self._channel_switch_fn = channel_switch_fn
        self._collector = DtmfCollector()

    def on_dtmf(self, digit: str) -> None:
        """Handle one received DTMF digit.

        Args:
            digit: The received DTMF character.
        """
        if self._dtmf_event_fn is not None:
            self._dtmf_event_fn(digit)
        result = self._collector.push(digit)
        if result is None:
            return
        if is_valid_channel(result, self._mode):
            logger.info("Switching to channel %d", result)
            self._retune(result)
            self._announce(f"Channel {result}")
            if self._channel_switch_fn is not None:
                self._channel_switch_fn(result)
        else:
            logger.warning("Invalid channel requested: %d", result)
            self._announce("Invalid channel")
