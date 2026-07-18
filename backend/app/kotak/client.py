"""
Kotak Neo REST client wrapper.

UNVERIFIED: endpoint paths and response field names are written from general knowledge
of Kotak Neo's published Trade API and are marked accordingly. Confirm against your own
API reference before trading on a funded account. See README.md and docs/SECURITY.md
for the confirmation-token gate that must wrap every call to place_order/modify_order/
cancel_order — this client itself does not enforce that gate, the order router does.
"""

import logging

import httpx

from app.config import Settings
from app.kotak.auth import KotakAuthenticator
from app.kotak.exceptions import KotakApiError

logger = logging.getLogger("mt5bridge.kotak.client")


class KotakClient:
    def __init__(self, settings: Settings, authenticator: KotakAuthenticator, http_client: httpx.AsyncClient):
        self._settings = settings
        self._auth = authenticator
        self._http = http_client

    async def _headers(self) -> dict[str, str]:
        session = await self._auth.get_session()
        return {
            "Authorization": f"Bearer {session.session_token}",
            "sid": session.sid,
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        headers = await self._headers()
        headers.update(kwargs.pop("headers", {}))
        url = f"{self._settings.kotak_neo_base_url}{path}"
        try:
            resp = await self._http.request(method, url, headers=headers, timeout=10.0, **kwargs)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise KotakApiError(
                f"Kotak Neo API error on {method} {path}: {exc}",
                status_code=exc.response.status_code,
                payload=_safe_json(exc.response),
            ) from exc
        except httpx.HTTPError as exc:
            raise KotakApiError(f"Kotak Neo API request failed on {method} {path}: {exc}") from exc
        return resp.json()

    # --- read endpoints  [UNVERIFIED paths/response shapes] -----------------------------------

    async def get_positions(self) -> list[dict]:
        data = await self._request("GET", "/orders/1.0/positions")
        return data.get("data", data.get("positions", []))

    async def get_holdings(self) -> list[dict]:
        data = await self._request("GET", "/portfolio/1.0/holdings")
        return data.get("data", data.get("holdings", []))

    async def get_margins(self) -> dict:
        data = await self._request("GET", "/orders/1.0/margins")
        return data.get("data", data)

    # --- write endpoints  [UNVERIFIED paths/payload shapes] ------------------------------------
    # Callers MUST have already validated a confirmation token before reaching these methods —
    # see backend/app/routers/orders.py. This client performs no such check itself.

    async def place_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str,
        product: str,
        price: float | None,
    ) -> dict:
        payload = {
            "tradingSymbol": symbol,
            "transactionType": side,
            "quantity": quantity,
            "orderType": order_type,
            "product": product,
            "price": price if price is not None else 0,
        }
        return await self._request("POST", "/orders/1.0/orders", json=payload)

    async def modify_order(self, *, kotak_order_id: str, quantity: int | None, price: float | None) -> dict:
        payload = {"orderId": kotak_order_id}
        if quantity is not None:
            payload["quantity"] = quantity
        if price is not None:
            payload["price"] = price
        return await self._request("PUT", f"/orders/1.0/orders/{kotak_order_id}", json=payload)

    async def cancel_order(self, *, kotak_order_id: str) -> dict:
        return await self._request("DELETE", f"/orders/1.0/orders/{kotak_order_id}")


def _safe_json(response: httpx.Response) -> dict:
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text[:500]}
