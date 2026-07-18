import asyncio
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.metrics import WS_CLIENTS_CONNECTED
from app.redis_client import get_redis
from app.security import decode_token

router = APIRouter(tags=["websocket"])
logger = logging.getLogger("mt5bridge.ws")


async def _authenticate_ws(ws: WebSocket, token: str | None) -> bool:
    if not token:
        await ws.close(code=4401, reason="missing token")
        return False
    try:
        decode_token(token)
    except Exception:
        await ws.close(code=4401, reason="invalid or expired token")
        return False
    return True


async def _pubsub_relay(ws: WebSocket, channels: list[str], endpoint_label: str) -> None:
    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(*channels)
    WS_CLIENTS_CONNECTED.labels(endpoint=endpoint_label).inc()
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30.0)
            if message is not None:
                await ws.send_text(message["data"])
            else:
                await ws.send_text(json.dumps({"type": "ping"}))
    finally:
        WS_CLIENTS_CONNECTED.labels(endpoint=endpoint_label).dec()
        await pubsub.unsubscribe(*channels)
        await pubsub.close()


@router.websocket("/ws/ticks")
async def ws_ticks(ws: WebSocket, token: str | None = Query(None)):
    await ws.accept()
    if not await _authenticate_ws(ws, token):
        return

    try:
        subscribe_msg = await asyncio.wait_for(ws.receive_json(), timeout=10.0)
        symbols = subscribe_msg.get("subscribe", [])
    except (asyncio.TimeoutError, WebSocketDisconnect):
        symbols = []

    if not symbols:
        await ws.close(code=4400, reason="expected {\"subscribe\": [symbols]} as first message")
        return

    channels = [f"ticks:{s}" for s in symbols]
    try:
        await _pubsub_relay(ws, channels, "ticks")
    except WebSocketDisconnect:
        logger.info("ws_ticks client disconnected")


@router.websocket("/ws/portfolio")
async def ws_portfolio(ws: WebSocket, token: str | None = Query(None)):
    await ws.accept()
    if not await _authenticate_ws(ws, token):
        return
    try:
        await _pubsub_relay(ws, ["portfolio:updates"], "portfolio")
    except WebSocketDisconnect:
        logger.info("ws_portfolio client disconnected")


@router.websocket("/ws/orders")
async def ws_orders(ws: WebSocket, token: str | None = Query(None)):
    await ws.accept()
    if not await _authenticate_ws(ws, token):
        return
    try:
        await _pubsub_relay(ws, ["orders:events"], "orders")
    except WebSocketDisconnect:
        logger.info("ws_orders client disconnected")
