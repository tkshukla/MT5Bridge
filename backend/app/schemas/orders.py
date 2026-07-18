from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ManualOrderRequest(BaseModel):
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0)
    order_type: Literal["MARKET", "LIMIT", "SL", "SL-M"]
    price: float | None = None
    product: str
    confirmation_token: str
    confirmed_at: datetime

    @field_validator("price")
    @classmethod
    def price_required_for_limit(cls, v: float | None, info) -> float | None:
        order_type = info.data.get("order_type")
        if order_type in ("LIMIT", "SL") and v is None:
            raise ValueError("price is required for LIMIT/SL orders")
        return v


class ModifyOrderRequest(BaseModel):
    order_id: str
    quantity: int | None = Field(default=None, gt=0)
    price: float | None = None
    confirmation_token: str
    confirmed_at: datetime


class ClosePositionRequest(BaseModel):
    symbol: str
    product: str
    quantity: int | None = Field(default=None, gt=0)
    confirmation_token: str
    confirmed_at: datetime


class OrderOut(BaseModel):
    id: str
    kotak_order_id: str | None
    symbol: str
    side: str
    order_type: str
    product: str
    quantity: int
    price: float | None
    action: str
    status: str
    reject_reason: str | None
    created_at: datetime
