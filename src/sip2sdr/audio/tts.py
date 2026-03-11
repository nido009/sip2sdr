"""Text-to-speech announcement generator using espeak-ng.

Pre-generates and caches common channel announcements at startup to
minimise latency when a caller switches channels.  Audio is output as
8000 Hz mono int16 PCM, matching the PCMU codec used in the SIP layer.
"""

from __future__ import annotations

import hashlib
import io
import logging
import subprocess
import wave
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

ESPEAK_BIN = "espeak-ng"
SAMPLE_RATE = 8000  # Hz — must match PCMU codec


class TtsError(Exception):
    """Raised when espeak-ng fails to generate audio."""


class TtsEngine:
    """Generates and caches TTS announcements via espeak-ng.

    Args:
        cache_dir: Directory where rendered PCM files are stored.
    """

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory: dict[str, NDArray[np.int16]] = {}

    def generate(self, text: str) -> NDArray[np.int16]:
        """Return 8000 Hz mono int16 PCM for *text*, using cache if available.

        Args:
            text: The announcement text to synthesise.

        Returns:
            1-D int16 numpy array of audio samples at 8000 Hz.

        Raises:
            TtsError: if espeak-ng cannot be invoked or fails.
        """
        if text in self._memory:
            return self._memory[text]

        cache_file = self._cache_path(text)
        if not cache_file.exists():
            self._render(text, cache_file)

        audio = np.fromfile(cache_file, dtype=np.int16)
        self._memory[text] = audio
        return audio

    def prewarm(self, channels: list[int]) -> None:
        """Pre-generate announcements for *channels* to fill the cache.

        Args:
            channels: List of channel numbers to pre-render.
        """
        for ch in channels:
            text = f"Channel {ch}"
            logger.info("Pre-warming TTS cache for %r", text)
            self.generate(text)
        self.generate("Invalid channel")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _cache_path(self, text: str) -> Path:
        key = hashlib.md5(text.encode()).hexdigest()  # noqa: S324
        return self._cache_dir / f"{key}.pcm"

    def _render(self, text: str, output: Path) -> None:
        """Invoke espeak-ng and write raw int16 PCM to *output*."""
        try:
            result = subprocess.run(
                [
                    ESPEAK_BIN,
                    "-v", "en",
                    "-s", "140",
                    "-a", "100",
                    "--stdout",
                    text,
                ],
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise TtsError(f"espeak-ng binary not found: {ESPEAK_BIN}") from exc
        if result.returncode != 0:
            raise TtsError(
                f"espeak-ng failed (rc={result.returncode}): "
                f"{result.stderr.decode(errors='replace')}"
            )

        audio = _wav_bytes_to_pcm8k(result.stdout)
        audio.tofile(output)


def _wav_bytes_to_pcm8k(wav_bytes: bytes) -> NDArray[np.int16]:
    """Convert WAV bytes (from espeak-ng stdout) to 8000 Hz int16 PCM.

    espeak-ng outputs 22050 Hz 16-bit mono by default; we resample to 8000 Hz.
    """
    with wave.open(io.BytesIO(wav_bytes)) as wf:
        n_channels = wf.getnchannels()
        framerate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())

    samples = np.frombuffer(raw, dtype=np.int16).copy()

    # Mix down to mono if needed.
    if n_channels > 1:
        samples = samples.reshape(-1, n_channels).mean(axis=1).astype(np.int16)

    # Resample to 8000 Hz using linear interpolation (good enough for speech).
    if framerate != SAMPLE_RATE:
        n_out = int(len(samples) * SAMPLE_RATE / framerate)
        x_old = np.linspace(0, 1, len(samples))
        x_new = np.linspace(0, 1, n_out)
        samples = np.interp(x_new, x_old, samples).astype(np.int16)

    return samples
