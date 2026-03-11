"""Marine VHF and LPD433 channel frequency tables.

Marine VHF follows the ITU channel plan (156.0–162.025 MHz, 25 kHz spacing).
LPD433 covers 433.075–434.775 MHz with 25 kHz spacing (69 channels).
"""

from enum import Enum


class ChannelMode(Enum):
    """Operating mode determining the channel plan in use."""

    MARINE = "marine"
    TEST = "test"


# ITU Marine VHF channel plan — subset of commonly used channels.
# Full plan: channels 1-88, with some gaps and duplex pairs.
# Frequencies given in MHz for the simplex / ship transmit frequency.
_MARINE_CHANNELS: dict[int, float] = {
    1: 156.050,
    2: 156.100,
    3: 156.150,
    4: 156.200,
    5: 156.250,
    6: 156.300,
    7: 156.350,
    8: 156.400,
    9: 156.450,
    10: 156.500,
    11: 156.550,
    12: 156.600,
    13: 156.650,
    14: 156.700,
    15: 156.750,
    16: 156.800,
    17: 156.850,
    18: 156.900,
    19: 156.950,
    20: 157.000,
    21: 157.050,
    22: 157.100,
    23: 157.150,
    24: 157.200,
    25: 157.250,
    26: 157.300,
    27: 157.350,
    28: 157.400,
    60: 156.025,
    61: 156.075,
    62: 156.125,
    63: 156.175,
    64: 156.225,
    65: 156.275,
    66: 156.325,
    67: 156.375,
    68: 156.425,
    69: 156.475,
    70: 156.525,
    71: 156.575,
    72: 156.625,
    73: 156.675,
    74: 156.725,
    75: 156.775,
    76: 156.825,
    77: 156.875,
    78: 156.925,
    79: 156.975,
    80: 157.025,
    81: 157.075,
    82: 157.125,
    83: 157.175,
    84: 157.225,
    85: 157.275,
    86: 157.325,
    87: 157.375,
    88: 157.425,
}

# LPD433 channel plan: 433.075 MHz base, 25 kHz spacing, 69 channels.
_LPD_CHANNELS: dict[int, float] = {
    ch: round(433.075 + (ch - 1) * 0.025, 6) for ch in range(1, 70)
}

_CHANNEL_TABLES: dict[ChannelMode, dict[int, float]] = {
    ChannelMode.MARINE: _MARINE_CHANNELS,
    ChannelMode.TEST: _LPD_CHANNELS,
}


def get_channel_table(mode: ChannelMode) -> dict[int, float]:
    """Return the full channel-number → frequency (MHz) table for *mode*."""
    return _CHANNEL_TABLES[mode]


def get_channel_frequency(channel: int, mode: ChannelMode) -> float:
    """Return the frequency in MHz for *channel* in *mode*.

    Raises:
        KeyError: if the channel number is not in the table.
    """
    return _CHANNEL_TABLES[mode][channel]


def is_valid_channel(channel: int, mode: ChannelMode) -> bool:
    """Return True if *channel* exists in the *mode* channel table."""
    return channel in _CHANNEL_TABLES[mode]
