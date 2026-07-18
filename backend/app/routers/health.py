from fastapi import APIRouter, Request

from app.db import check_db_ok
from app.redis_client import check_redis_ok
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    feed = getattr(request.app.state, "kotak_feed", None)
    db_ok = await check_db_ok()
    redis_ok = await check_redis_ok()
    return HealthResponse(
        status="ok" if (db_ok and redis_ok) else "degraded",
        kotak_feed="connected" if feed and feed.connected else "disconnected",
        db="ok" if db_ok else "unreachable",
        redis="ok" if redis_ok else "unreachable",
    )
