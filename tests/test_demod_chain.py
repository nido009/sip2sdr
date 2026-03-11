"""Tests for the NFM demodulator chain."""

import pytest

gnuradio = pytest.importorskip("gnuradio", reason="GNU Radio not available")

from sip2sdr.audio.ring_buffer import RingBuffer  # noqa: E402
from sip2sdr.sdr.demod_chain import DemodChain  # noqa: E402


class TestDemodChain:
    def test_construction(self) -> None:
        buf = RingBuffer(capacity=4000)
        chain = DemodChain(
            center_freq_offset=156.375e6 - 159e6,
            sdr_sample_rate=8_000_000,
            channel_bandwidth=12_500,
            buf=buf,
        )
        assert chain is not None

    def test_initial_center_freq_offset(self) -> None:
        buf = RingBuffer(capacity=4000)
        offset = 156.375e6 - 159e6
        chain = DemodChain(
            center_freq_offset=offset,
            sdr_sample_rate=8_000_000,
            channel_bandwidth=12_500,
            buf=buf,
        )
        assert chain.center_freq_offset == pytest.approx(offset)

    def test_retune(self) -> None:
        buf = RingBuffer(capacity=4000)
        chain = DemodChain(
            center_freq_offset=0.0,
            sdr_sample_rate=8_000_000,
            channel_bandwidth=12_500,
            buf=buf,
        )
        new_offset = 156.800e6 - 159e6
        chain.retune(new_offset)
        assert chain.center_freq_offset == pytest.approx(new_offset)

    def test_squelch_block_present(self) -> None:
        from gnuradio import analog
        buf = RingBuffer(capacity=4000)
        chain = DemodChain(
            center_freq_offset=0.0,
            sdr_sample_rate=8_000_000,
            channel_bandwidth=12_500,
            buf=buf,
            squelch_threshold_db=-20.0,
        )
        assert chain.squelch_block is not None
        assert isinstance(chain.squelch_block, analog.standard_squelch_ff)

    def test_squelch_default_threshold(self) -> None:
        buf = RingBuffer(capacity=4000)
        chain = DemodChain(
            center_freq_offset=0.0,
            sdr_sample_rate=8_000_000,
            channel_bandwidth=12_500,
            buf=buf,
        )
        assert chain.squelch_block.threshold() == pytest.approx(-20.0)

    def test_set_squelch_threshold(self) -> None:
        buf = RingBuffer(capacity=4000)
        chain = DemodChain(
            center_freq_offset=0.0,
            sdr_sample_rate=8_000_000,
            channel_bandwidth=12_500,
            buf=buf,
        )
        chain.set_squelch_threshold(-35.0)
        assert chain.squelch_block.threshold() == pytest.approx(-35.0)
