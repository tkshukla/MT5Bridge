from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Symbol(Base):
    __tablename__ = "symbols"

    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    exchange: Mapped[str] = mapped_column(String, nullable=False)
    segment: Mapped[str] = mapped_column(String, nullable=False)
    kotak_exchange_segment: Mapped[str] = mapped_column(String, nullable=False)
    instrument_token: Mapped[str | None] = mapped_column(String, nullable=True)
    underlying: Mapped[str | None] = mapped_column(String, nullable=True)
    expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    strike: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    option_type: Mapped[str | None] = mapped_column(String, nullable=True)
    lot_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tick_size: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0.05)
    mt5_symbol_name: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
