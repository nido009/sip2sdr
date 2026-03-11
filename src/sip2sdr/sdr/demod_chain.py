"""Single NFM demodulator chain for one Marine VHF or LPD433 channel.

Each chain consists of:
1. Frequency-translating FIR filter — selects one channel from the wideband IQ
2. NFM demodulator — demodulates narrowband FM
3. Rational resampler — converts to 8000 Hz
4. Ring buffer sink — writes PCM samples for the SIP layer to consume

The chain is designed to be embedded in a GNU Radio top block; it does
not own its own flowgraph.
"""

from __future__ import annotations

import logging
from math import gcd

import numpy as np
from gnuradio import analog, gr
from gnuradio import filter as grfilter
from gnuradio.filter import firdes

from sip2sdr.audio.ring_buffer import RingBuffer

logger = logging.getLogger(__name__)

_OUTPUT_RATE = 8_000   # Hz — PCMU sample rate
_CHANNEL_RATE = 50_000  # Hz — intermediate rate after freq_xlat decimation


class _RingBufferSink(gr.sync_block):
    """GNU Radio sink block that writes float32 samples into a RingBuffer as int16."""

    def __init__(self, buf: RingBuffer) -> None:
        super().__init__(
            name="RingBufferSink",
            in_sig=[np.float32],
            out_sig=[],
        )
        self._buf = buf

    def work(self, input_items: list, output_items: list) -> int:
        """Process incoming float32 samples and write int16 PCM to the ring buffer."""
        samples = np.array(input_items[0], dtype=np.float32)
        clipped = np.clip(samples, -1.0, 1.0)
        pcm = (clipped * 32767).astype(np.int16)
        self._buf.write(pcm)
        return len(samples)


class DemodChain:
    """One NFM demodulator pipeline for a single channel.

    Args:
        center_freq_offset: Frequency offset from SDR center frequency (Hz).
            Negative values mean the channel is below the SDR center.
        sdr_sample_rate: Sample rate of the wideband IQ input (samples/sec).
        channel_bandwidth: One-sided bandwidth of the channel filter (Hz).
            Typically 12500 for 25 kHz channel spacing.
        buf: Ring buffer to write decoded 8kHz PCM samples into.
        squelch_threshold_db: Squelch threshold in dB (default -20.0).
            More negative opens squelch on weaker signals. Uses power-based
            squelch detection (analog.pwr_squelch_ff).
    """

    def __init__(
        self,
        center_freq_offset: float,
        sdr_sample_rate: int,
        channel_bandwidth: int,
        buf: RingBuffer,
        squelch_threshold_db: float = -20.0,
    ) -> None:
        self._center_freq_offset = center_freq_offset
        self._sdr_sample_rate = sdr_sample_rate
        self._buf = buf

        # Decimate in the freq_xlating filter to reach a manageable channel rate.
        # _CHANNEL_RATE must divide evenly into sdr_sample_rate.
        xlat_decim = sdr_sample_rate // _CHANNEL_RATE
        channel_rate = sdr_sample_rate // xlat_decim

        taps = firdes.low_pass(
            gain=1.0,
            sampling_freq=sdr_sample_rate,
            cutoff_freq=channel_bandwidth,
            transition_width=channel_bandwidth * 0.5,
        )
        self._xlat = grfilter.freq_xlating_fir_filter_ccc(
            decimation=xlat_decim,
            taps=taps,
            center_freq=center_freq_offset,
            sampling_freq=sdr_sample_rate,
        )

        fm_deviation = channel_bandwidth
        self._nfm = analog.fm_demod_cf(
            channel_rate=channel_rate,
            audio_decim=1,
            deviation=fm_deviation,
            audio_pass=3_000,
            audio_stop=4_000,
            gain=1.0,
            tau=75e-6,
        )

        self._squelch = analog.pwr_squelch_ff(squelch_threshold_db)

        g = gcd(channel_rate, _OUTPUT_RATE)
        interp = _OUTPUT_RATE // g
        decim = channel_rate // g
        self._resamp = grfilter.rational_resampler_fff(
            interpolation=interp,
            decimation=decim,
        )

        self._sink = _RingBufferSink(buf)

    @property
    def center_freq_offset(self) -> float:
        """Current frequency offset from SDR center frequency (Hz)."""
        return self._center_freq_offset

    @property
    def xlat_block(self) -> grfilter.freq_xlating_fir_filter_ccc:
        """The frequency-translating FIR filter block (for flowgraph connection)."""
        return self._xlat

    @property
    def sink_block(self) -> _RingBufferSink:
        """The ring buffer sink block (for flowgraph connection)."""
        return self._sink

    @property
    def nfm_block(self) -> analog.fm_demod_cf:
        """The NFM demodulator block."""
        return self._nfm

    @property
    def squelch_block(self) -> analog.pwr_squelch_ff:
        """The squelch block (for flowgraph connection and threshold adjustment)."""
        return self._squelch

    @property
    def resamp_block(self) -> grfilter.rational_resampler_fff:
        """The rational resampler block."""
        return self._resamp

    def retune(self, new_offset: float) -> None:
        """Update the channel centre frequency offset without stopping the flowgraph.

        Args:
            new_offset: New frequency offset from SDR centre frequency (Hz).
        """
        self._center_freq_offset = new_offset
        self._xlat.set_center_freq(new_offset)
        logger.info("Retuned demod chain to offset %.3f kHz", new_offset / 1e3)

    def set_squelch_threshold(self, threshold_db: float) -> None:
        """Update the squelch threshold without stopping the flowgraph.

        Args:
            threshold_db: New threshold in dB. More negative = more sensitive.
        """
        self._squelch.set_threshold(threshold_db)
        logger.debug("Squelch threshold set to %.1f dB", threshold_db)
