import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.redis_client import get_redis
from app.schemas.market import Quote
from app.security import Role, require_role

router = APIRouter(tags=["market-data"])


@router.get("/quotes/{symbol}", response_model=Quote)
async def get_quote(symbol: str, _=Depends(require_role(Role.VIEWER))) -> Quote:
    redis = get_redis()
    raw = await redis.get(f"tick:{symbol}")
    if raw is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"no cached quote for {symbol}")
    data = json.loads(raw)
    return Quote(
        symbol=symbol,
        ltp=data["ltp"],
        bid=data.get("bid"),
        ask=data.get("ask"),
        volume=data.get("volume"),
        ts=data.get("ts", datetime.now(timezone.utc).isoformat()),
    )
