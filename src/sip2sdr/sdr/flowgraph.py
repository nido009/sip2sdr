"""GNU Radio wideband flowgraph for SIP2SDR.

Instantiates the HackRF source and up to 4 NFM demodulator chains
(xlat → NFM → squelch → resamp → ring buffer), connects them within a
single top block, and provides a ``retune`` method for live channel
switching.
"""

from __future__ import annotations

import logging

from gnuradio import gr
from osmosdr import source as osmosdr_source

from sip2sdr.audio.ring_buffer import RingBuffer
from sip2sdr.channels import ChannelMode, get_channel_frequency
from sip2sdr.sdr.demod_chain import DemodChain

logger = logging.getLogger(__name__)

# Centre frequencies for the two operating modes.
_CENTER_FREQ: dict[ChannelMode, float] = {
    ChannelMode.MARINE: 159.0e6,  # covers 156.0–162.025 MHz at 8 Msps
    ChannelMode.TEST: 433.9e6,  # covers 433.075–434.775 MHz at 2 Msps
}

_CHANNEL_BW = 12_500  # Hz — one-sided bandwidth (25 kHz channel spacing)


class SdrFlowgraph(gr.top_block):
    """Wideband HackRF capture with 4 independent NFM demodulator chains.

    Args:
        mode: Operating mode (MARINE or TEST).
        sdr_device_args: osmosdr device string, e.g. ``"hackrf=0"``.
        sample_rate: ADC sample rate in samples/second.
        gain_lna: LNA gain in dB.
        gain_vga: VGA gain in dB.
        gain_amp: Enable RF amplifier.
        initial_channels: List of 4 channel numbers to tune at startup.
        buffers: List of 4 RingBuffer instances (one per chain).
        squelch_threshold_db: Squelch threshold in dB (default -20.0).
            More negative opens squelch on weaker signals.
    """

    def __init__(
        self,
        mode: ChannelMode,
        sdr_device_args: str,
        sample_rate: int,
        gain_lna: int,
        gain_vga: int,
        gain_amp: bool,
        initial_channels: list[int],
        buffers: list[RingBuffer],
        squelch_threshold_db: float = -20.0,
    ) -> None:
        super().__init__("SIP2SDR Flowgraph")

        if len(initial_channels) != 4 or len(buffers) != 4:
            raise ValueError("Exactly 4 channels and 4 buffers are required")

        self._mode = mode
        self._center_freq = _CENTER_FREQ[mode]

        self._src = osmosdr_source(args=sdr_device_args)
        self._src.set_sample_rate(sample_rate)
        self._src.set_center_freq(self._center_freq)
        self._src.set_gain(gain_lna, "LNA")
        self._src.set_gain(gain_vga, "VGA")
        self._src.set_gain(1 if gain_amp else 0, "AMP")
        self._src.set_freq_corr(0)

        self._chains: list[DemodChain] = []
        for i, (ch, buf) in enumerate(zip(initial_channels, buffers, strict=True)):
            freq = get_channel_frequency(ch, mode) * 1e6
            offset = freq - self._center_freq
            chain = DemodChain(
                center_freq_offset=offset,
                sdr_sample_rate=sample_rate,
                channel_bandwidth=_CHANNEL_BW,
                buf=buf,
                squelch_threshold_db=squelch_threshold_db,
            )
            self._chains.append(chain)
            self.connect(self._src, chain.xlat_block)
            self.connect(chain.xlat_block, chain.nfm_block)
            self.connect(chain.nfm_block, chain.squelch_block)
            self.connect(chain.squelch_block, chain.resamp_block)
            self.connect(chain.resamp_block, chain.sink_block)
            logger.info("Chain %d: channel %d (%.3f MHz)", i, ch, freq / 1e6)

    @property
    def center_frequency(self) -> float:
        """SDR centre frequency in Hz."""
        return self._center_freq

    @property
    def chains(self) -> list[DemodChain]:
        """The 4 demodulator chains."""
        return self._chains

    def retune(self, chain_index: int, channel: int) -> None:
        """Retune one demodulator chain to a new channel.

        Args:
            chain_index: 0-based index of the chain to retune (0–3).
            channel: Target channel number (validated against the channel table).
        """
        freq = get_channel_frequency(channel, self._mode) * 1e6
        offset = freq - self._center_freq
        self._chains[chain_index].retune(offset)
        logger.info(
            "Chain %d retuned to channel %d (%.3f MHz, offset %.3f kHz)",
            chain_index,
            channel,
            freq / 1e6,
            offset / 1e3,
        )
