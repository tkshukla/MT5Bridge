from datetime import datetime

from pydantic import BaseModel


class PositionOut(BaseModel):
    symbol: str
    product: str
    quantity: int
    avg_price: float
    ltp: float | None
    unrealized_pnl: float | None
    realized_pnl: float | None
    snapshot_at: datetime


class HoldingOut(BaseModel):
    symbol: str
    quantity: int
    avg_price: float
    ltp: float | None
    current_value: float | None
    pnl: float | None
    snapshot_at: datetime


class MarginsOut(BaseModel):
    cash_available: float
    margin_used: float
    total_value: float


class PortfolioOut(BaseModel):
    total_value: float
    cash_available: float
    margin_used: float
    day_pnl: float
    open_pnl: float
    realized_pnl: float
    snapshot_at: datetime
