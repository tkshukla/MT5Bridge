"""
Kotak Neo live tick feed, via `neo_api_client`'s `subscribe()` + callback mechanism
(confirmed against `neo-api-client==2.0.0`).

The SDK registers `on_message`/`on_error`/`on_close`/`on_open` as plain instance
attributes (per `NeoAPI.__init__`'s docstring) and runs its own WebSocket connection
in a background thread — NOT the asyncio event loop. Callbacks therefore push onto a
thread-safe `queue.Queue`; an asyncio task drains that queue and calls the async
`on_tick` handler.

UNVERIFIED: the exact `instrument_tokens` item shape `subscribe()` expects, and the
exact `on_message` payload shape, were not confirmed against a live feed (that would
require an active market-hours connection, out of scope for a dry integration check).
This assumes a list of `{"instrument_token": ..., "exchange_segment": ...}` dicts (the
`symbols` table's `instrument_token`/`kotak_exchange_segment` columns) and a message
payload with `tsym`/`ltp`/`v` fields, based on Kotak Neo's commonly-documented feed
format — verify against a real subscription and adjust `_handle_message` if the field
names differ.
"""

import asyncio
import logging
import queue
import threading
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from app.kotak.auth import KotakSessionManager
from app.metrics import KOTAK_FEED_CONNECTED, TICKS_RECEIVED_TOTAL

logger = logging.getLogger("mt5bridge.kotak.feed")

TickHandler = Callable[[dict], Awaitable[None]]


class KotakWebSocketFeed:
    def __init__(self, session_manager: KotakSessionManager, on_tick: TickHandler):
        self._sessions = session_manager
        self._on_tick = on_tick
        self._queue: queue.Queue = queue.Queue()
        self._subscriptions: list[dict] = []
        self._stop = threading.Event()
        self._connected = False

    def set_subscriptions(self, subscriptions: list[dict]) -> None:
        """subscriptions: [{"instrument_token": ..., "exchange_segment": ...}, ...]"""
        self._subscriptions = subscriptions

    @property
    def connected(self) -> bool:
        return self._connected

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        while not self._stop.is_set():
            if not self._sessions.is_authenticated:
                await asyncio.sleep(2)
                continue
            try:
                await self._subscribe_and_drain()
            except Exception:
                self._connected = False
                KOTAK_FEED_CONNECTED.set(0)
                logger.exception("Kotak Neo feed error; retrying in 5s")
                await asyncio.sleep(5)

    async def _subscribe_and_drain(self) -> None:
        client = self._sessions.get_client()

        def _on_message(message):
            self._queue.put(("message", message))

        def _on_error(error):
            self._queue.put(("error", error))

        def _on_close(*_args):
            self._queue.put(("close", None))

        def _on_open(*_args):
            self._queue.put(("open", None))

        client.on_message = _on_message
        client.on_error = _on_error
        client.on_close = _on_close
        client.on_open = _on_open
        client.set_neowebsocket_callbacks()

        if self._subscriptions:
            await asyncio.to_thread(client.subscribe, instrument_tokens=self._subscriptions)

        self._connected = True
        KOTAK_FEED_CONNECTED.set(1)
        logger.info("Kotak Neo feed subscribed (%d instruments)", len(self._subscriptions))

        while not self._stop.is_set():
            try:
                kind, payload = await asyncio.to_thread(self._queue.get, True, 1.0)
            except queue.Empty:
                continue
            if kind == "message":
                await self._handle_message(payload)
            elif kind == "error":
                raise RuntimeError(f"Kotak Neo feed error callback: {payload}")
            elif kind == "close":
                raise RuntimeError("Kotak Neo feed closed")
            # "open" needs no action — self._connected is already set above.

    async def _handle_message(self, message) -> None:
        if not isinstance(message, dict):
            return

        # UNVERIFIED field names — see module docstring.
        symbol = message.get("tsym") or message.get("trading_symbol") or message.get("symbol")
        ltp = message.get("ltp") or message.get("last_traded_price")
        if not symbol or ltp is None:
            return

        try:
            ltp = float(ltp)
        except (TypeError, ValueError):
            return

        tick = {
            "symbol": symbol,
            "ltp": ltp,
            "bid": message.get("bp1") or message.get("bid"),
            "ask": message.get("sp1") or message.get("ask"),
            "volume": message.get("v") or message.get("volume"),
            "ts": message.get("ft") or datetime.now(timezone.utc).isoformat(),
        }
        TICKS_RECEIVED_TOTAL.labels(symbol=symbol).inc()
        await self._on_tick(tick)
