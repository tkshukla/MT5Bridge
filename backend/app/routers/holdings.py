from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Holding
from app.schemas.portfolio import HoldingOut
from app.security import Role, require_role

router = APIRouter(tags=["portfolio"])


@router.get("/holdings", response_model=list[HoldingOut])
async def get_holdings(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(Role.VIEWER)),
) -> list[HoldingOut]:
    rows = (await db.execute(select(Holding))).scalars().all()
    return [HoldingOut.model_validate(row, from_attributes=True) for row in rows]
