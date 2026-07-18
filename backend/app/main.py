import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.config import get_settings
from app.kotak.auth import KotakSessionManager
from app.kotak.client import KotakClient
from app.kotak.websocket_feed import KotakWebSocketFeed
from app.metrics import HTTP_REQUEST_LATENCY
from app.routers import auth, health, holdings, margins, ohlc, orders, portfolio, positions, quotes, symbols, ws
from app.security import Role, require_role
from app.workers import handle_tick, poll_portfolio_once

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("mt5bridge")


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_manager = KotakSessionManager(settings)
    kotak_client = KotakClient(session_manager)
    feed = KotakWebSocketFeed(session_manager, on_tick=handle_tick)

    app.state.kotak_session_manager = session_manager
    app.state.kotak_client = kotak_client
    app.state.kotak_feed = feed

    feed_task = asyncio.create_task(feed.run_forever())

    async def portfolio_poll_loop():
        while True:
            await poll_portfolio_once(kotak_client, session_manager)
            await asyncio.sleep(settings.kotak_neo_poll_interval_seconds)

    poll_task = asyncio.create_task(portfolio_poll_loop())

    logger.info(
        "MT5Bridge backend started (env=%s) — call POST /auth/kotak-login before reads/orders will work",
        settings.app_env,
    )
    try:
        yield
    finally:
        feed.stop()
        feed_task.cancel()
        poll_task.cancel()
        for task in (feed_task, poll_task):
            try:
                await task
            except asyncio.CancelledError:
                pass
        session_manager.logout()
        logger.info("MT5Bridge backend shut down")


app = FastAPI(
    title="MT5Bridge",
    description="MT5 <-> Kotak Neo bridge: read-only market/portfolio data, manual-confirmation-only orders.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
app.include_router(quotes.router, prefix="/api/v1")
app.include_router(positions.router, prefix="/api/v1")
app.include_router(holdings.router, prefix="/api/v1")
app.include_router(margins.router, prefix="/api/v1")
app.include_router(portfolio.router, prefix="/api/v1")
app.include_router(ohlc.router, prefix="/api/v1")
app.include_router(symbols.router, prefix="/api/v1")
app.include_router(orders.router, prefix="/api/v1")
app.include_router(ws.router)  # /ws/* — not under /api/v1 to keep WS URLs short


@app.middleware("http")
async def record_request_latency(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    HTTP_REQUEST_LATENCY.labels(
        method=request.method,
        path=request.url.path,
        status=str(response.status_code),
    ).observe(time.perf_counter() - start)
    return response


@app.get("/metrics")
async def metrics(request: Request, _=Depends(require_role(Role.VIEWER))) -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
