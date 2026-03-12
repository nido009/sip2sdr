"""Tests for the wideband GNU Radio flowgraph."""

import pytest

gnuradio = pytest.importorskip("gnuradio", reason="GNU Radio not available")

from sip2sdr.audio.ring_buffer import RingBuffer  # noqa: E402
from sip2sdr.channels import ChannelMode  # noqa: E402
from sip2sdr.sdr.flowgraph import SdrFlowgraph  # noqa: E402


class TestSdrFlowgraph:
    def test_construction_marine(self) -> None:
        buffers = [RingBuffer(4000) for _ in range(4)]
        fg = SdrFlowgraph(
            mode=ChannelMode.MARINE,
            sdr_device_args="hackrf=0",
            sample_rate=8_000_000,
            gain_lna=32,
            gain_vga=30,
            gain_amp=False,
            initial_channels=[67, 67, 67, 67],
            buffers=buffers,
        )
        assert fg is not None

    def test_construction_test_mode(self) -> None:
        buffers = [RingBuffer(4000) for _ in range(4)]
        fg = SdrFlowgraph(
            mode=ChannelMode.TEST,
            sdr_device_args="hackrf=0",
            sample_rate=2_000_000,
            gain_lna=32,
            gain_vga=30,
            gain_amp=False,
            initial_channels=[1, 1, 1, 1],
            buffers=buffers,
        )
        assert fg is not None

    def test_chains_have_squelch_block(self) -> None:
        """Each chain's squelch block is not None after flowgraph construction."""
        buffers = [RingBuffer(4000) for _ in range(4)]
        fg = SdrFlowgraph(
            mode=ChannelMode.TEST,
            sdr_device_args="hackrf=0",
            sample_rate=2_000_000,
            gain_lna=32,
            gain_vga=30,
            gain_amp=False,
            initial_channels=[1, 2, 3, 4],
            buffers=buffers,
            squelch_threshold_db=-20.0,
        )
        for chain in fg.chains:
            assert chain.squelch_block is not None

    def test_get_channel_states(self) -> None:
        buffers = [RingBuffer(4000) for _ in range(4)]
        fg = SdrFlowgraph(
            mode=ChannelMode.TEST,
            sdr_device_args="hackrf=0",
            sample_rate=2_000_000,
            gain_lna=32,
            gain_vga=30,
            gain_amp=False,
            initial_channels=[1, 2, 3, 4],
            buffers=buffers,
        )
        states = fg.get_channel_states()
        assert len(states) == 4
        for state in states:
            assert "signal_level_db" in state
            assert "squelch_open" in state
            assert "squelch_threshold_db" in state
            assert "channel_offset_hz" in state
            assert isinstance(state["signal_level_db"], float)
            assert isinstance(state["squelch_open"], bool)
            assert isinstance(state["squelch_threshold_db"], float)
            assert isinstance(state["channel_offset_hz"], float)

    def test_set_squelch_threshold_on_flowgraph(self) -> None:
        buffers = [RingBuffer(4000) for _ in range(4)]
        fg = SdrFlowgraph(
            mode=ChannelMode.TEST,
            sdr_device_args="hackrf=0",
            sample_rate=2_000_000,
            gain_lna=32,
            gain_vga=30,
            gain_amp=False,
            initial_channels=[1, 1, 1, 1],
            buffers=buffers,
            squelch_threshold_db=-20.0,
        )
        fg.set_squelch_threshold(0, -40.0)
        assert fg.chains[0].squelch_threshold == pytest.approx(-40.0)
        assert fg.chains[1].squelch_threshold == pytest.approx(-20.0)

    def test_retune_channel(self) -> None:
        buffers = [RingBuffer(4000) for _ in range(4)]
        fg = SdrFlowgraph(
            mode=ChannelMode.MARINE,
            sdr_device_args="hackrf=0",
            sample_rate=8_000_000,
            gain_lna=32,
            gain_vga=30,
            gain_amp=False,
            initial_channels=[67, 67, 67, 67],
            buffers=buffers,
        )
        fg.retune(chain_index=0, channel=16)
        from sip2sdr.channels import get_channel_frequency  # noqa: E402

        expected_freq = get_channel_frequency(16, ChannelMode.MARINE) * 1e6
        center = fg.center_frequency
        assert abs(fg.chains[0].center_freq_offset - (expected_freq - center)) < 1
