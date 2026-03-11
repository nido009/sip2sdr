"""Tests for espeak-ng TTS announcement generator."""

from pathlib import Path

import numpy as np
import pytest

from sip2sdr.audio.tts import TtsEngine, TtsError


class TestTtsEngine:
    def test_generate_returns_int16_array(self, tmp_path: Path) -> None:
        tts = TtsEngine(cache_dir=tmp_path)
        audio = tts.generate("Channel 16")
        assert audio.dtype == np.int16
        assert audio.ndim == 1
        assert len(audio) > 0

    def test_generate_caches_result(self, tmp_path: Path) -> None:
        tts = TtsEngine(cache_dir=tmp_path)
        audio1 = tts.generate("Channel 16")
        audio2 = tts.generate("Channel 16")
        np.testing.assert_array_equal(audio1, audio2)

    def test_cache_files_are_written(self, tmp_path: Path) -> None:
        tts = TtsEngine(cache_dir=tmp_path)
        tts.generate("Channel 67")
        assert any(tmp_path.iterdir())

    def test_different_texts_differ(self, tmp_path: Path) -> None:
        tts = TtsEngine(cache_dir=tmp_path)
        a = tts.generate("Channel 16")
        b = tts.generate("Channel 67")
        # Different texts should produce different audio.
        assert not np.array_equal(a, b)

    def test_prewarm_generates_channel_cache(self, tmp_path: Path) -> None:
        tts = TtsEngine(cache_dir=tmp_path)
        tts.prewarm(channels=[16, 67])
        files = list(tmp_path.iterdir())
        assert len(files) >= 2

    def test_invalid_espeak_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import sip2sdr.audio.tts as tts_mod
        monkeypatch.setattr(tts_mod, "ESPEAK_BIN", "/nonexistent/espeak-ng")
        tts = TtsEngine(cache_dir=tmp_path)
        with pytest.raises(TtsError):
            tts.generate("test")
