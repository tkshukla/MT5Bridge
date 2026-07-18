from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Position
from app.schemas.portfolio import PositionOut
from app.security import Role, require_role

router = APIRouter(tags=["portfolio"])


@router.get("/positions", response_model=list[PositionOut])
async def get_positions(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(Role.VIEWER)),
) -> list[PositionOut]:
    rows = (await db.execute(select(Position))).scalars().all()
    return [PositionOut.model_validate(row, from_attributes=True) for row in rows]
