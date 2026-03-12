"""Tests for the debug web server REST endpoints and WebSocket state format."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from aiohttp.test_utils import TestClient, TestServer

from sip2sdr.web.server import create_debug_app


def _make_mock_flowgraph(num_chains: int = 4) -> MagicMock:
    fg = MagicMock()
    fg.get_channel_states.return_value = [
        {
            "signal_level_db": -45.0,
            "squelch_open": False,
            "squelch_threshold_db": -20.0,
            "channel_offset_hz": -2_625_000.0,
        }
        for _ in range(num_chains)
    ]
    return fg


def _make_mock_sip(num_accounts: int = 4) -> MagicMock:
    sip = MagicMock()
    sip.get_account_states.return_value = [
        {
            "is_in_call": False,
            "remote_uri": "",
            "call_duration_s": 0.0,
            "current_channel": 67,
            "dtmf_history": [],
        }
        for _ in range(num_accounts)
    ]
    return sip


@pytest.mark.asyncio
async def test_get_index_returns_html() -> None:
    fg = _make_mock_flowgraph()
    sip = _make_mock_sip()
    app = create_debug_app(fg, sip)
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/")
        assert resp.status == 200
        assert "text/html" in resp.content_type
        text = await resp.text()
        assert "<html" in text.lower()


@pytest.mark.asyncio
async def test_post_squelch_valid() -> None:
    fg = _make_mock_flowgraph()
    sip = _make_mock_sip()
    app = create_debug_app(fg, sip)
    async with TestClient(TestServer(app)) as client:
        resp = await client.post(
            "/api/squelch", json={"channel_idx": 0, "threshold_db": -35.0}
        )
        assert resp.status == 200
        fg.set_squelch_threshold.assert_called_once_with(0, -35.0)


@pytest.mark.asyncio
async def test_post_squelch_invalid_index() -> None:
    fg = _make_mock_flowgraph()
    sip = _make_mock_sip()
    app = create_debug_app(fg, sip)
    async with TestClient(TestServer(app)) as client:
        resp = await client.post(
            "/api/squelch", json={"channel_idx": 99, "threshold_db": -35.0}
        )
        assert resp.status == 400


@pytest.mark.asyncio
async def test_post_squelch_missing_fields() -> None:
    fg = _make_mock_flowgraph()
    sip = _make_mock_sip()
    app = create_debug_app(fg, sip)
    async with TestClient(TestServer(app)) as client:
        resp = await client.post("/api/squelch", json={"channel_idx": 0})
        assert resp.status == 400


@pytest.mark.asyncio
async def test_post_retune_valid() -> None:
    fg = _make_mock_flowgraph()
    sip = _make_mock_sip()
    app = create_debug_app(fg, sip)
    async with TestClient(TestServer(app)) as client:
        resp = await client.post(
            "/api/retune", json={"channel_idx": 1, "channel_number": 16}
        )
        assert resp.status == 200
        fg.retune.assert_called_once_with(1, 16)


@pytest.mark.asyncio
async def test_post_retune_invalid_index() -> None:
    fg = _make_mock_flowgraph()
    sip = _make_mock_sip()
    app = create_debug_app(fg, sip)
    async with TestClient(TestServer(app)) as client:
        resp = await client.post(
            "/api/retune", json={"channel_idx": -1, "channel_number": 16}
        )
        assert resp.status == 400


@pytest.mark.asyncio
async def test_post_retune_missing_fields() -> None:
    fg = _make_mock_flowgraph()
    sip = _make_mock_sip()
    app = create_debug_app(fg, sip)
    async with TestClient(TestServer(app)) as client:
        resp = await client.post("/api/retune", json={"channel_idx": 0})
        assert resp.status == 400


@pytest.mark.asyncio
async def test_websocket_state_format() -> None:
    fg = _make_mock_flowgraph()
    sip = _make_mock_sip()
    app = create_debug_app(fg, sip)
    async with TestClient(TestServer(app)) as client:
        async with client.ws_connect("/ws") as ws:
            msg = await asyncio.wait_for(ws.receive_json(), timeout=2.0)
            assert "channels" in msg
            assert "accounts" in msg
            assert len(msg["channels"]) == 4
            assert len(msg["accounts"]) == 4
            ch = msg["channels"][0]
            assert "signal_level_db" in ch
            assert "squelch_open" in ch
            assert "squelch_threshold_db" in ch
            assert "channel_offset_hz" in ch
            acc = msg["accounts"][0]
            assert "is_in_call" in acc
            assert "remote_uri" in acc
            assert "call_duration_s" in acc
            assert "current_channel" in acc
            assert "dtmf_history" in acc
