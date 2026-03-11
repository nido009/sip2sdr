"""PJSUA2 custom media port that reads audio from a RingBuffer.

Each active SIP call has one RingBufferMediaPort connected to the
demodulator chain's ring buffer.  PJSUA2 calls ``onFrameRequested()``
every 20 ms (160 samples at 8000 Hz) to pull audio for transmission to
the caller.
"""

from __future__ import annotations

import logging

import pjsua2 as pj

from sip2sdr.audio.ring_buffer import RingBuffer

logger = logging.getLogger(__name__)


class RingBufferMediaPort(pj.AudioMediaPort):
    """PJSUA2 AudioMediaPort that sources audio from a RingBuffer.

    Args:
        buf: Ring buffer populated by a GNU Radio demodulator chain.
        sample_rate: Audio sample rate in Hz (must be 8000 for PCMU).
        samples_per_frame: Number of samples per 20 ms frame (160 for 8 kHz).
    """

    def __init__(self, buf: RingBuffer, sample_rate: int, samples_per_frame: int) -> None:
        super().__init__()
        self._buf = buf
        self._samples_per_frame = samples_per_frame

        fmt = pj.MediaFormatAudio()
        fmt.type = pj.PJMEDIA_TYPE_AUDIO
        fmt.clockRate = sample_rate
        fmt.channelCount = 1
        fmt.bitsPerSample = 16
        fmt.frameTimeUsec = 20_000  # 20 ms

        self.createPort("sip2sdr", fmt)

    def onFrameRequested(self, frame: pj.MediaFrame) -> None:  # type: ignore[override]
        """Fill *frame* with PCM audio from the ring buffer.

        Called by PJSUA2 every 20 ms.  If the ring buffer underruns,
        the frame is filled with silence.

        Args:
            frame: PJSUA2 MediaFrame to fill with audio data.
        """
        samples = self._buf.read(self._samples_per_frame)
        frame.buf = samples.tobytes()

    def getFrame(self) -> bytes:
        """Return one frame of PCM audio as bytes (for testing).

        Returns:
            Raw bytes of int16 PCM samples (samples_per_frame * 2 bytes).
        """
        samples = self._buf.read(self._samples_per_frame)
        return samples.tobytes()
