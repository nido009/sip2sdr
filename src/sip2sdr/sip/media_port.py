"""PJSUA2 custom media port that reads audio from a RingBuffer.

Each active SIP call has one RingBufferMediaPort connected to the
demodulator chain's ring buffer.  PJSUA2 calls ``onFrameRequested()``
every 20 ms (160 samples at 8000 Hz) to pull audio for transmission to
the caller.

TTS announcements are played by writing PCM samples into the TTS buffer.
``_read_frame`` always drains the TTS buffer first; once it is empty the
caller hears SDR audio again with no explicit pause/resume required.
"""

from __future__ import annotations

import logging

import numpy as np
from numpy.typing import NDArray

from sip2sdr.audio.ring_buffer import RingBuffer

logger = logging.getLogger(__name__)


def _read_frame(
    sdr_buf: RingBuffer,
    tts_buf: RingBuffer,
    n: int,
) -> NDArray[np.int16]:
    """Read one audio frame, preferring TTS audio over SDR audio.

    Args:
        sdr_buf: Ring buffer fed by the GNU Radio demodulator chain.
        tts_buf: Ring buffer fed by TTS announcements.
        n: Number of samples to return.

    Returns:
        Array of exactly *n* int16 samples.
    """
    if tts_buf.available > 0:
        return tts_buf.read(n)
    return sdr_buf.read(n)


try:
    import pjsua2 as pj

    class RingBufferMediaPort(pj.AudioMediaPort):
        """PJSUA2 AudioMediaPort that sources audio from a RingBuffer.

        TTS announcements take priority: when *tts_buf* contains samples they
        are played first; once drained, SDR audio from *sdr_buf* resumes
        automatically.

        Args:
            sdr_buf: Ring buffer populated by a GNU Radio demodulator chain.
            tts_buf: Ring buffer populated by TTS announcement audio.
            sample_rate: Audio sample rate in Hz (must be 8000 for G.711).
            samples_per_frame: Number of samples per 20 ms frame (160 for 8 kHz).
        """

        def __init__(
            self,
            sdr_buf: RingBuffer,
            tts_buf: RingBuffer,
            sample_rate: int,
            samples_per_frame: int,
        ) -> None:
            super().__init__()
            self._sdr_buf = sdr_buf
            self._tts_buf = tts_buf
            self._samples_per_frame = samples_per_frame

            fmt = pj.MediaFormatAudio()
            fmt.type = pj.PJMEDIA_TYPE_AUDIO
            fmt.clockRate = sample_rate
            fmt.channelCount = 1
            fmt.bitsPerSample = 16
            fmt.frameTimeUsec = 20_000  # 20 ms

            self.createPort("sip2sdr", fmt)

        def onFrameRequested(self, frame: pj.MediaFrame) -> None:  # type: ignore[override]
            """Fill *frame* with PCM audio, prioritising TTS over SDR.

            Called by PJSUA2 every 20 ms.

            Args:
                frame: PJSUA2 MediaFrame to fill with audio data.
            """
            samples = _read_frame(self._sdr_buf, self._tts_buf, self._samples_per_frame)
            frame.buf = samples.tobytes()

        def getFrame(self) -> bytes:
            """Return one frame of PCM audio as bytes (for testing).

            Returns:
                Raw bytes of int16 PCM samples (samples_per_frame * 2 bytes).
            """
            samples = _read_frame(self._sdr_buf, self._tts_buf, self._samples_per_frame)
            return samples.tobytes()

except ModuleNotFoundError:
    logger.debug("pjsua2 not available; RingBufferMediaPort will not be defined")
