"""
Kotak Neo WebSocket tick feed consumer.

UNVERIFIED: the subscribe-message shape and tick payload fields are written from
general knowledge of Kotak Neo's published WebSocket feed pattern (subscribe with a
list of instrument tokens, receive per-tick JSON frames). Confirm against your own API
reference before relying on this feed. See README.md disclaimer.
"""

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable, Awaitable
from datetime import datetime, timezone

import websockets
from websockets.exceptions import ConnectionClosed

from app.config import Settings
from app.kotak.auth import KotakAuthenticator
from app.metrics import KOTAK_FEED_CONNECTED, TICKS_RECEIVED_TOTAL

logger = logging.getLogger("mt5bridge.kotak.feed")

TickHandler = Callable[[dict], Awaitable[None]]


class KotakWebSocketFeed:
    def __init__(self, settings: Settings, authenticator: KotakAuthenticator, on_tick: TickHandler):
        self._settings = settings
        self._auth = authenticator
        self._on_tick = on_tick
        self._subscribed_tokens: set[str] = set()
        self._stop = asyncio.Event()
        self._connected = False

    def set_subscriptions(self, instrument_tokens: set[str]) -> None:
        self._subscribed_tokens = instrument_tokens

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                await self._connect_and_consume()
                backoff = 1.0
            except (ConnectionClosed, OSError) as exc:
                self._connected = False
                KOTAK_FEED_CONNECTED.set(0)
                logger.warning("Kotak Neo feed disconnected (%s); reconnecting in %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
            except Exception:
                self._connected = False
                KOTAK_FEED_CONNECTED.set(0)
                logger.exception("Unexpected error in Kotak Neo feed loop; reconnecting in %.1fs", backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    @property
    def connected(self) -> bool:
        return self._connected

    async def _connect_and_consume(self) -> None:
        session = await self._auth.get_session()
        url = f"{self._settings.kotak_neo_ws_url}?sid={session.sid}"
        async with websockets.connect(url, extra_headers={"Authorization": f"Bearer {session.session_token}"}) as ws:
            self._connected = True
            KOTAK_FEED_CONNECTED.set(1)
            logger.info("Connected to Kotak Neo WebSocket feed")

            if self._subscribed_tokens:
                await ws.send(json.dumps({"type": "subscribe", "tokens": sorted(self._subscribed_tokens)}))

            heartbeat_task = asyncio.create_task(self._heartbeat(ws))
            try:
                async for raw_message in ws:
                    if self._stop.is_set():
                        break
                    await self._handle_message(raw_message)
            finally:
                heartbeat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat_task

    async def _heartbeat(self, ws) -> None:
        while True:
            await asyncio.sleep(20)
            with contextlib.suppress(Exception):
                await ws.send(json.dumps({"type": "ping"}))

    async def _handle_message(self, raw_message: str | bytes) -> None:
        try:
            message = json.loads(raw_message)
        except (json.JSONDecodeError, TypeError):
            return
        if message.get("type") != "tick":
            return

        symbol = message.get("symbol") or message.get("tradingSymbol")
        ltp = message.get("ltp") or message.get("last_price")
        if not symbol or ltp is None:
            return

        tick = {
            "symbol": symbol,
            "ltp": float(ltp),
            "bid": message.get("bid"),
            "ask": message.get("ask"),
            "volume": message.get("volume"),
            "ts": message.get("ts") or datetime.now(timezone.utc).isoformat(),
        }
        TICKS_RECEIVED_TOTAL.labels(symbol=symbol).inc()
        await self._on_tick(tick)
