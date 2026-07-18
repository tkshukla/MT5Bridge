"""
Kotak Neo authentication, via the official `neo_api_client` SDK (confirmed against
`neo-api-client==2.0.0` by inspecting the installed package directly — see
CHANGELOG/commit history for how this was verified).

The real login flow is two calls on a `NeoAPI` instance:
  1. `totp_login(mobile_number, ucc, totp)` — mobile number + UCC (Unique Client Code)
     + the 6-digit authenticator TOTP code.
  2. `totp_validate(mpin)` — the account's 6-digit MPIN.

TOTP and MPIN are NOT static secrets — TOTP is a fresh 6-digit code every 30 seconds,
and MPIN, while stable, is a login credential this codebase does not store (same
policy as never storing a broker password). Both are supplied live, per login, via
`POST /auth/kotak-login` (see routers/auth.py) — never persisted in `.env` or the
database. `consumer_key`/`neo_fin_key`/`ucc`/`mobile_number` are static per-app/
per-account identifiers and do live in `.env`.

The resulting `NeoAPI` instance (holding its own access/session token internally)
is cached in memory only, for the lifetime of the backend process. Restarting the
backend requires calling `/auth/kotak-login` again.
"""

import asyncio
import logging

from neo_api_client import NeoAPI

from app.config import Settings
from app.kotak.exceptions import KotakAuthError

logger = logging.getLogger("mt5bridge.kotak.auth")


class KotakSessionManager:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client: NeoAPI | None = None
        self._ucc: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return self._client is not None

    @property
    def ucc(self) -> str | None:
        return self._ucc

    def get_client(self) -> NeoAPI:
        if self._client is None:
            raise KotakAuthError("not logged in to Kotak Neo — call POST /auth/kotak-login first")
        return self._client

    async def login(self, totp: str, mpin: str) -> dict:
        """Performs totp_login + totp_validate. Returns a small, secret-free summary dict."""
        s = self._settings
        if not (s.kotak_neo_consumer_key and s.kotak_neo_ucc and s.kotak_neo_mobile_number):
            raise KotakAuthError(
                "KOTAK_NEO_CONSUMER_KEY / KOTAK_NEO_UCC / KOTAK_NEO_MOBILE_NUMBER must be set in .env"
            )

        def _do_login() -> dict:
            client = NeoAPI(
                environment=s.kotak_neo_environment,
                consumer_key=s.kotak_neo_consumer_key,
                consumer_secret=s.kotak_neo_consumer_secret or None,
                neo_fin_key=s.kotak_neo_neo_fin_key or None,
            )
            login_resp = client.totp_login(mobile_number=s.kotak_neo_mobile_number, ucc=s.kotak_neo_ucc, totp=totp)
            if not isinstance(login_resp, dict) or "data" not in login_resp:
                raise KotakAuthError(f"unexpected totp_login response shape: {login_resp}")

            validate_resp = client.totp_validate(mpin=mpin)
            if not isinstance(validate_resp, dict) or "data" not in validate_resp:
                raise KotakAuthError(f"unexpected totp_validate response shape: {validate_resp}")

            return {"client": client, "data": validate_resp["data"]}

        try:
            result = await asyncio.to_thread(_do_login)
        except KotakAuthError:
            raise
        except Exception as exc:
            raise KotakAuthError(f"Kotak Neo login failed: {exc}") from exc

        self._client = result["client"]
        self._ucc = result["data"].get("ucc", s.kotak_neo_ucc)
        logger.info("Kotak Neo login successful for UCC=%s", self._ucc)
        return {"ucc": self._ucc, "greeting_name": result["data"].get("greetingName")}

    def logout(self) -> None:
        if self._client is not None:
            try:
                self._client.logout()
            except Exception:
                logger.exception("error during Kotak Neo logout (continuing anyway)")
        self._client = None
        self._ucc = None
