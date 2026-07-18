from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import PortfolioSnapshot
from app.schemas.portfolio import PortfolioOut
from app.security import Role, require_role

router = APIRouter(tags=["portfolio"])


@router.get("/portfolio", response_model=PortfolioOut)
async def get_portfolio(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(Role.VIEWER)),
) -> PortfolioOut:
    latest = (
        await db.execute(select(PortfolioSnapshot).order_by(PortfolioSnapshot.snapshot_at.desc()).limit(1))
    ).scalar_one_or_none()
    if latest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no portfolio snapshot yet")
    return PortfolioOut.model_validate(latest, from_attributes=True)
