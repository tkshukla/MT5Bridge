from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Candle as CandleModel
from app.schemas.market import Candle
from app.security import Role, require_role

router = APIRouter(tags=["market-data"])


@router.get("/ohlc/{symbol}", response_model=list[Candle])
async def get_ohlc(
    symbol: str,
    timeframe: str = Query("5m"),
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(Role.VIEWER)),
) -> list[Candle]:
    stmt = select(CandleModel).where(CandleModel.symbol == symbol, CandleModel.timeframe == timeframe)
    if from_ is not None:
        stmt = stmt.where(CandleModel.ts_open >= from_)
    if to is not None:
        stmt = stmt.where(CandleModel.ts_open <= to)
    stmt = stmt.order_by(CandleModel.ts_open.asc())

    rows = (await db.execute(stmt)).scalars().all()
    return [Candle.model_validate(row, from_attributes=True) for row in rows]
