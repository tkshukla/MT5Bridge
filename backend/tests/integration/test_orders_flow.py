from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.kotak.exceptions import KotakApiError
from app.security import Role, create_access_token


class FakeKotakClient:
    """Stands in for KotakClient — no network call ever reaches Kotak Neo in these tests."""

    def __init__(self, *, reject: bool = False):
        self.reject = reject
        self.place_order_calls: list[dict] = []

    async def place_order(self, **kwargs):
        self.place_order_calls.append(kwargs)
        if self.reject:
            raise KotakApiError("insufficient margin", status_code=409)
        return {"orderId": "KN-TEST-1"}


def _trader_headers():
    token = create_access_token("mt5-desktop-test", Role.TRADER)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_manual_order_accepted_and_audited(client, seed_symbol):
    from app.main import app

    fake_kotak = FakeKotakClient(reject=False)
    app.state.kotak_client = fake_kotak

    payload = {
        "symbol": "NIFTY24JULFUT",
        "side": "BUY",
        "quantity": 50,
        "order_type": "MARKET",
        "product": "MIS",
        "confirmation_token": "unique-token-1",
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
    resp = await client.post("/api/v1/manual-order", json=payload, headers=_trader_headers())

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "PLACED"
    assert body["kotak_order_id"] == "KN-TEST-1"
    assert len(fake_kotak.place_order_calls) == 1


@pytest.mark.asyncio
async def test_manual_order_rejected_by_broker_returns_409(client, seed_symbol):
    from app.main import app

    app.state.kotak_client = FakeKotakClient(reject=True)

    payload = {
        "symbol": "NIFTY24JULFUT",
        "side": "BUY",
        "quantity": 50,
        "order_type": "MARKET",
        "product": "MIS",
        "confirmation_token": "unique-token-2",
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
    resp = await client.post("/api/v1/manual-order", json=payload, headers=_trader_headers())
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_manual_order_replayed_token_rejected(client, seed_symbol):
    from app.main import app

    app.state.kotak_client = FakeKotakClient(reject=False)

    payload = {
        "symbol": "NIFTY24JULFUT",
        "side": "BUY",
        "quantity": 50,
        "order_type": "MARKET",
        "product": "MIS",
        "confirmation_token": "reused-token",
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
    first = await client.post("/api/v1/manual-order", json=payload, headers=_trader_headers())
    assert first.status_code == 201

    second = await client.post("/api/v1/manual-order", json=payload, headers=_trader_headers())
    assert second.status_code == 422
    assert "already used" in second.json()["detail"]


@pytest.mark.asyncio
async def test_manual_order_stale_confirmation_rejected(client, seed_symbol):
    from app.main import app

    app.state.kotak_client = FakeKotakClient(reject=False)

    payload = {
        "symbol": "NIFTY24JULFUT",
        "side": "BUY",
        "quantity": 50,
        "order_type": "MARKET",
        "product": "MIS",
        "confirmation_token": "stale-token",
        "confirmed_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
    }
    resp = await client.post("/api/v1/manual-order", json=payload, headers=_trader_headers())
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_manual_order_wrong_lot_size_rejected(client, seed_symbol):
    from app.main import app

    app.state.kotak_client = FakeKotakClient(reject=False)

    payload = {
        "symbol": "NIFTY24JULFUT",
        "side": "BUY",
        "quantity": 51,  # lot size is 50
        "order_type": "MARKET",
        "product": "MIS",
        "confirmation_token": "lot-size-token",
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
    resp = await client.post("/api/v1/manual-order", json=payload, headers=_trader_headers())
    assert resp.status_code == 422
    assert "lot size" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_manual_order_requires_trader_role(client, seed_symbol):
    from app.main import app

    app.state.kotak_client = FakeKotakClient(reject=False)
    viewer_token = create_access_token("viewer-user", Role.VIEWER)

    payload = {
        "symbol": "NIFTY24JULFUT",
        "side": "BUY",
        "quantity": 50,
        "order_type": "MARKET",
        "product": "MIS",
        "confirmation_token": "viewer-token",
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
    resp = await client.post(
        "/api/v1/manual-order", json=payload, headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert resp.status_code == 403
