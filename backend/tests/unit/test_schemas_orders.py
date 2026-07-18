from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.orders import ManualOrderRequest


def _base_payload(**overrides):
    payload = {
        "symbol": "NIFTY24JULFUT",
        "side": "BUY",
        "quantity": 50,
        "order_type": "MARKET",
        "product": "MIS",
        "confirmation_token": "tok123",
        "confirmed_at": datetime.now(timezone.utc),
    }
    payload.update(overrides)
    return payload


def test_market_order_does_not_require_price():
    order = ManualOrderRequest(**_base_payload())
    assert order.price is None


def test_limit_order_requires_price():
    with pytest.raises(ValidationError):
        ManualOrderRequest(**_base_payload(order_type="LIMIT", price=None))


def test_limit_order_with_price_is_valid():
    order = ManualOrderRequest(**_base_payload(order_type="LIMIT", price=24500.5))
    assert order.price == 24500.5


def test_zero_quantity_rejected():
    with pytest.raises(ValidationError):
        ManualOrderRequest(**_base_payload(quantity=0))


def test_invalid_side_rejected():
    with pytest.raises(ValidationError):
        ManualOrderRequest(**_base_payload(side="HOLD"))
