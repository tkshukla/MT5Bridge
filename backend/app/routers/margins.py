from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import PortfolioSnapshot
from app.schemas.portfolio import MarginsOut
from app.security import Role, require_role

router = APIRouter(tags=["portfolio"])


@router.get("/margins", response_model=MarginsOut)
async def get_margins(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(Role.VIEWER)),
) -> MarginsOut:
    latest = (
        await db.execute(select(PortfolioSnapshot).order_by(PortfolioSnapshot.snapshot_at.desc()).limit(1))
    ).scalar_one_or_none()
    if latest is None:
        return MarginsOut(cash_available=0.0, margin_used=0.0, total_value=0.0)
    return MarginsOut(
        cash_available=latest.cash_available,
        margin_used=latest.margin_used,
        total_value=latest.total_value,
    )
