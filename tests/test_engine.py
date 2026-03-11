"""Tests for the PJSUA2 SIP account manager."""

from unittest.mock import MagicMock

import pytest

pjsua2 = pytest.importorskip("pjsua2", reason="pjsua2 not available")

from sip2sdr.config import ExtensionConfig, SipConfig  # noqa: E402
from sip2sdr.sip.engine import SipEngine  # noqa: E402


class TestSipEngine:
    def _make_sip_config(self) -> SipConfig:
        return SipConfig(
            registrar="sip:pbx.example.com",
            transport="tls",
            srtp="required",
            verify_certs=False,
            extensions=[
                ExtensionConfig("sip2sdr-1", "secret1", 67),
                ExtensionConfig("sip2sdr-2", "secret2", 67),
            ],
        )

    def test_construction(self) -> None:
        cfg = self._make_sip_config()
        buffers = [MagicMock(), MagicMock()]
        retune_fns = [MagicMock(), MagicMock()]
        engine = SipEngine(sip_config=cfg, buffers=buffers, retune_fns=retune_fns, tts=MagicMock())
        assert engine is not None

    def test_extension_count_matches_config(self) -> None:
        cfg = self._make_sip_config()
        buffers = [MagicMock(), MagicMock()]
        retune_fns = [MagicMock(), MagicMock()]
        engine = SipEngine(sip_config=cfg, buffers=buffers, retune_fns=retune_fns, tts=MagicMock())
        assert engine.num_extensions == 2
