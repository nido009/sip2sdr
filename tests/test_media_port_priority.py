"""Tests for TTS priority read logic in the media port (no pjsua2 required)."""

import numpy as np

from sip2sdr.audio.ring_buffer import RingBuffer
from sip2sdr.sip.media_port import _read_frame


class TestReadFrame:
    def test_reads_tts_when_available(self) -> None:
        sdr_buf = RingBuffer(capacity=4000)
        tts_buf = RingBuffer(capacity=4000)
        sdr_buf.write(np.full(160, 1, dtype=np.int16))
        tts_buf.write(np.full(160, 99, dtype=np.int16))
        result = _read_frame(sdr_buf=sdr_buf, tts_buf=tts_buf, n=160)
        assert result[0] == 99  # TTS takes priority

    def test_falls_back_to_sdr_when_tts_empty(self) -> None:
        sdr_buf = RingBuffer(capacity=4000)
        tts_buf = RingBuffer(capacity=4000)
        sdr_buf.write(np.full(160, 7, dtype=np.int16))
        result = _read_frame(sdr_buf=sdr_buf, tts_buf=tts_buf, n=160)
        assert result[0] == 7  # SDR fallback

    def test_returns_silence_when_both_empty(self) -> None:
        sdr_buf = RingBuffer(capacity=4000)
        tts_buf = RingBuffer(capacity=4000)
        result = _read_frame(sdr_buf=sdr_buf, tts_buf=tts_buf, n=160)
        np.testing.assert_array_equal(result, np.zeros(160, dtype=np.int16))

    def test_tts_drains_then_sdr_resumes(self) -> None:
        sdr_buf = RingBuffer(capacity=4000)
        tts_buf = RingBuffer(capacity=4000)
        sdr_buf.write(np.full(320, 7, dtype=np.int16))
        tts_buf.write(np.full(160, 99, dtype=np.int16))  # only one frame of TTS
        first = _read_frame(sdr_buf=sdr_buf, tts_buf=tts_buf, n=160)
        second = _read_frame(sdr_buf=sdr_buf, tts_buf=tts_buf, n=160)
        assert first[0] == 99   # TTS
        assert second[0] == 7   # back to SDR
