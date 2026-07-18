from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Symbol
from app.schemas.market import SymbolInfo
from app.security import Role, require_role

router = APIRouter(tags=["market-data"])


@router.get("/symbols", response_model=list[SymbolInfo])
async def list_symbols(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(Role.VIEWER)),
) -> list[SymbolInfo]:
    rows = (await db.execute(select(Symbol).where(Symbol.is_active.is_(True)))).scalars().all()
    return [
        SymbolInfo(
            symbol=row.symbol,
            exchange=row.exchange,
            segment=row.segment,
            underlying=row.underlying,
            expiry=row.expiry.isoformat() if row.expiry else None,
            strike=row.strike,
            option_type=row.option_type,
            lot_size=row.lot_size,
            tick_size=row.tick_size,
            mt5_symbol_name=row.mt5_symbol_name,
            is_active=row.is_active,
        )
        for row in rows
    ]
