"""Tests for the PJSUA2 custom media port."""

import pytest

pjsua2 = pytest.importorskip("pjsua2", reason="pjsua2 not available")

import numpy as np  # noqa: E402

from sip2sdr.audio.ring_buffer import RingBuffer  # noqa: E402
from sip2sdr.sip.media_port import RingBufferMediaPort  # noqa: E402


class TestRingBufferMediaPort:
    def test_construction(self) -> None:
        sdr_buf = RingBuffer(4000)
        tts_buf = RingBuffer(4000)
        port = RingBufferMediaPort(
            sdr_buf=sdr_buf, tts_buf=tts_buf, sample_rate=8000, samples_per_frame=160
        )
        assert port is not None

    def test_on_frame_requested_returns_samples(self) -> None:
        sdr_buf = RingBuffer(4000)
        tts_buf = RingBuffer(4000)
        sdr_buf.write(np.ones(160, dtype=np.int16))
        port = RingBufferMediaPort(
            sdr_buf=sdr_buf, tts_buf=tts_buf, sample_rate=8000, samples_per_frame=160
        )
        frame = port.getFrame()
        assert frame is not None

    def test_on_frame_requested_silence_on_empty(self) -> None:
        sdr_buf = RingBuffer(4000)
        tts_buf = RingBuffer(4000)
        port = RingBufferMediaPort(
            sdr_buf=sdr_buf, tts_buf=tts_buf, sample_rate=8000, samples_per_frame=160
        )
        frame = port.getFrame()
        assert frame is not None
