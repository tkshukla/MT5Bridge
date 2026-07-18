from datetime import datetime

from pydantic import BaseModel


class Quote(BaseModel):
    symbol: str
    ltp: float
    bid: float | None = None
    ask: float | None = None
    volume: int | None = None
    ts: datetime


class Candle(BaseModel):
    symbol: str
    timeframe: str
    ts_open: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    is_final: bool


class SymbolInfo(BaseModel):
    symbol: str
    exchange: str
    segment: str
    underlying: str | None
    expiry: str | None
    strike: float | None
    option_type: str | None
    lot_size: int
    tick_size: float
    mt5_symbol_name: str
    is_active: bool
