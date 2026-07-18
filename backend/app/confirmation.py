"""
Order confirmation-token validation — the core of the no-automated-execution guarantee.

The token itself is minted client-side by the MQL5 EA only after a user dismisses a
confirmation dialog (see mql5/Include/MT5Bridge/BridgeClient.mqh). This module only
validates that: (a) the confirmation happened recently (anti-replay TTL), and (b) the
token hasn't already been used for a previous order (enforced by a unique index on
orders.confirmation_token_hash at insert time — see db/schema.sql).
"""

import hashlib
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.config import get_settings

settings = get_settings()


def hash_confirmation_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def assert_confirmation_fresh(confirmed_at: datetime) -> None:
    if confirmed_at.tzinfo is None:
        confirmed_at = confirmed_at.replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - confirmed_at).total_seconds()
    if age_seconds < 0 or age_seconds > settings.order_token_ttl_seconds:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"confirmation expired or has an invalid timestamp (age={age_seconds:.1f}s, "
            f"ttl={settings.order_token_ttl_seconds}s)",
        )
