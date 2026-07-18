import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String, ForeignKey("symbols.symbol"), nullable=False)
    product: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_price: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    ltp: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    unrealized_pnl: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    realized_pnl: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    kotak_position_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
