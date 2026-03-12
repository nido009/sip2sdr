"""aiohttp debug web server for SIP2SDR.

Serves a single-page dashboard and a WebSocket endpoint that pushes
system state (signal levels, squelch, call status, DTMF history) every
250 ms to all connected browsers.

REST endpoints allow adjusting squelch thresholds and retuning channels
from the browser.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from sip2sdr.sdr.flowgraph import SdrFlowgraph
    from sip2sdr.sip.engine import SipEngine

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 0.25  # seconds between WebSocket state pushes
_DASHBOARD_HTML = Path(__file__).parent / "dashboard.html"
_NUM_CHAINS = 4

# Typed application keys (avoids aiohttp NotAppKeyWarning)
_KEY_FLOWGRAPH:  web.AppKey[SdrFlowgraph]                       = web.AppKey("flowgraph")
_KEY_SIP_ENGINE: web.AppKey[SipEngine]                          = web.AppKey("sip_engine")
_KEY_WS_CLIENTS: web.AppKey[set[web.WebSocketResponse]]         = web.AppKey("ws_clients")


def create_debug_app(flowgraph: SdrFlowgraph, sip_engine: SipEngine) -> web.Application:
    """Create the aiohttp Application for the debug dashboard.

    Separated from server lifecycle so tests can instantiate the app
    directly with ``aiohttp.test_utils``.

    Args:
        flowgraph: The running GNU Radio flowgraph (for SDR state queries).
        sip_engine: The SIP engine (for account/call state queries).

    Returns:
        Configured :class:`aiohttp.web.Application`.
    """
    app = web.Application()
    app[_KEY_FLOWGRAPH]  = flowgraph
    app[_KEY_SIP_ENGINE] = sip_engine
    app[_KEY_WS_CLIENTS] = set()

    app.router.add_get("/", _handle_index)
    app.router.add_get("/ws", _handle_ws)
    app.router.add_post("/api/squelch", _handle_squelch)
    app.router.add_post("/api/retune", _handle_retune)

    return app


async def _handle_index(request: web.Request) -> web.Response:
    """Serve the single-page HTML dashboard."""
    html = _DASHBOARD_HTML.read_text(encoding="utf-8")
    return web.Response(text=html, content_type="text/html")


async def _handle_ws(request: web.Request) -> web.WebSocketResponse:
    """WebSocket endpoint: push state JSON to client every 250 ms."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    clients: set[web.WebSocketResponse] = request.app[_KEY_WS_CLIENTS]
    clients.add(ws)
    logger.debug("WebSocket client connected (total=%d)", len(clients))

    try:
        # Push initial state immediately, then keep pushing until disconnected
        state_task = asyncio.create_task(_push_loop(ws, request.app))
        async for msg in ws:
            pass  # clients don't send messages; we only need to detect close
        state_task.cancel()
        try:
            await state_task
        except asyncio.CancelledError:
            pass
    finally:
        clients.discard(ws)
        logger.debug("WebSocket client disconnected (total=%d)", len(clients))

    return ws


async def _push_loop(ws: web.WebSocketResponse, app: web.Application) -> None:
    """Continuously push state JSON to a single WebSocket client."""
    while not ws.closed:
        state = _collect_state(app)
        try:
            await ws.send_str(json.dumps(state))
        except Exception:
            break
        await asyncio.sleep(_POLL_INTERVAL)


def _collect_state(app: web.Application) -> dict:
    """Collect current system state from flowgraph and SIP engine."""
    fg: SdrFlowgraph = app[_KEY_FLOWGRAPH]
    sip: SipEngine = app[_KEY_SIP_ENGINE]
    return {
        "channels": fg.get_channel_states(),
        "accounts": sip.get_account_states(),
    }


async def _handle_squelch(request: web.Request) -> web.Response:
    """POST /api/squelch — set squelch threshold for one chain.

    Expected JSON body: ``{"channel_idx": 0, "threshold_db": -35.0}``
    """
    try:
        body = await request.json()
        channel_idx = int(body["channel_idx"])
        threshold_db = float(body["threshold_db"])
    except (KeyError, TypeError, ValueError):
        return web.Response(status=400, text="Missing or invalid fields: channel_idx, threshold_db")

    if channel_idx < 0 or channel_idx >= _NUM_CHAINS:
        return web.Response(status=400, text=f"channel_idx must be 0–{_NUM_CHAINS - 1}")

    fg: SdrFlowgraph = request.app[_KEY_FLOWGRAPH]
    fg.set_squelch_threshold(channel_idx, threshold_db)
    logger.info("Web: squelch[%d] = %.1f dB", channel_idx, threshold_db)
    return web.Response(status=200, text="ok")


async def _handle_retune(request: web.Request) -> web.Response:
    """POST /api/retune — retune one chain to a new channel.

    Expected JSON body: ``{"channel_idx": 1, "channel_number": 16}``
    """
    try:
        body = await request.json()
        channel_idx = int(body["channel_idx"])
        channel_number = int(body["channel_number"])
    except (KeyError, TypeError, ValueError):
        return web.Response(status=400, text="Missing or invalid fields: channel_idx, channel_number")

    if channel_idx < 0 or channel_idx >= _NUM_CHAINS:
        return web.Response(status=400, text=f"channel_idx must be 0–{_NUM_CHAINS - 1}")

    fg: SdrFlowgraph = request.app[_KEY_FLOWGRAPH]
    fg.retune(channel_idx, channel_number)
    logger.info("Web: retune[%d] → channel %d", channel_idx, channel_number)
    return web.Response(status=200, text="ok")


class DebugWebServer:
    """Background debug web server for SIP2SDR.

    Runs an aiohttp server on a daemon thread with its own event loop.
    State is polled from the flowgraph and SIP engine every 250 ms and
    pushed as JSON to all connected WebSocket clients.

    Args:
        flowgraph: The running GNU Radio flowgraph.
        sip_engine: The SIP engine.
        port: TCP port to listen on (default 8080).
    """

    def __init__(
        self,
        flowgraph: SdrFlowgraph,
        sip_engine: SipEngine,
        port: int = 8080,
    ) -> None:
        self._flowgraph = flowgraph
        self._sip_engine = sip_engine
        self._port = port
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event = threading.Event()

    def start(self) -> None:
        """Start the web server in a background daemon thread."""
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="debug-web-server"
        )
        self._thread.start()
        logger.info("Debug web server starting on port %d", self._port)

    def stop(self) -> None:
        """Signal the server to shut down and wait for the thread to finish."""
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._stop_event.set)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        logger.info("Debug web server stopped")

    def _run(self) -> None:
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())

    async def _serve(self) -> None:
        app = create_debug_app(self._flowgraph, self._sip_engine)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self._port)
        await site.start()
        logger.info("Debug dashboard: http://0.0.0.0:%d/", self._port)

        # Poll until stop() is called
        loop = asyncio.get_running_loop()
        while not await loop.run_in_executor(None, self._stop_event.wait, 0.1):
            pass

        await runner.cleanup()
