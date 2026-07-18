import uuid
from datetime import datetime

from sqlalchemy import DateTime, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    total_value: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    cash_available: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    margin_used: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    day_pnl: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    open_pnl: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
