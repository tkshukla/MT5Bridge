"""
Kotak Neo REST-equivalent client, wrapping the official `neo_api_client` SDK
(confirmed against `neo-api-client==2.0.0`; see kotak/auth.py for the login flow).

`NeoAPI`'s methods are synchronous (built on `requests`), so every call here is
dispatched via `asyncio.to_thread` to avoid blocking the FastAPI event loop.

`validity` is hardcoded to "DAY" — MT5Bridge doesn't currently expose order validity
as a user-settable field (see docs/API.md). Revisit if you need IOC/other validities.
"""

import asyncio
import logging

from app.kotak.auth import KotakSessionManager
from app.kotak.exceptions import KotakApiError

logger = logging.getLogger("mt5bridge.kotak.client")

DEFAULT_VALIDITY = "DAY"


class KotakClient:
    def __init__(self, session_manager: KotakSessionManager):
        self._sessions = session_manager

    async def _call(self, fn_name: str, /, **kwargs):
        client = self._sessions.get_client()
        fn = getattr(client, fn_name)
        try:
            result = await asyncio.to_thread(fn, **kwargs)
        except Exception as exc:
            raise KotakApiError(f"Kotak Neo API error calling {fn_name}: {exc}") from exc

        if isinstance(result, dict) and result.get("stat") == "Not_Ok":
            raise KotakApiError(
                f"Kotak Neo rejected {fn_name}: {result.get('errMsg') or result}",
                payload=result,
            )
        return result

    # --- read endpoints ----------------------------------------------------------------

    async def get_positions(self) -> list[dict]:
        result = await self._call("positions")
        return result.get("data", []) if isinstance(result, dict) else (result or [])

    async def get_holdings(self) -> list[dict]:
        result = await self._call("holdings")
        return result.get("data", []) if isinstance(result, dict) else (result or [])

    async def get_margins(self) -> dict:
        result = await self._call("limits", segment="ALL", exchange="ALL", product="ALL")
        return result.get("data", result) if isinstance(result, dict) else {}

    # --- write endpoints -----------------------------------------------------------------
    # Callers MUST have already validated a confirmation token before reaching these methods
    # — see backend/app/routers/orders.py. This client performs no such check itself.

    async def place_order(
        self,
        *,
        symbol: str,
        kotak_exchange_segment: str,
        side: str,
        quantity: int,
        order_type: str,
        product: str,
        price: float | None,
    ) -> dict:
        result = await self._call(
            "place_order",
            exchange_segment=kotak_exchange_segment,
            product=product,
            price=price if price is not None else 0,
            order_type=order_type,
            quantity=quantity,
            validity=DEFAULT_VALIDITY,
            trading_symbol=symbol,
            transaction_type=side,
        )
        return result.get("data", result) if isinstance(result, dict) else {}

    async def modify_order(
        self,
        *,
        kotak_order_id: str,
        quantity: int | None,
        price: float | None,
        order_type: str,
    ) -> dict:
        result = await self._call(
            "modify_order",
            order_id=kotak_order_id,
            price=price if price is not None else 0,
            order_type=order_type,
            quantity=quantity,
            validity=DEFAULT_VALIDITY,
        )
        return result.get("data", result) if isinstance(result, dict) else {}

    async def cancel_order(self, *, kotak_order_id: str) -> dict:
        return await self._call("cancel_order", order_id=kotak_order_id)
