"""
Kotak Neo authentication (TOTP-based two-factor login).

UNVERIFIED: the exact login sequence, field names, and response shape below are
written from general knowledge of Kotak Neo's published API pattern (2-step login:
password grant, then TOTP validation, yielding a session token used as a bearer token
for subsequent calls). Verify against your own Kotak Neo API credentials/docs in a
sandbox before relying on this in production. See README.md and docs/SECURITY.md.
"""

import time
from dataclasses import dataclass

import httpx
import pyotp
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import Settings
from app.kotak.exceptions import KotakAuthError


@dataclass
class KotakSession:
    access_token: str
    session_token: str
    sid: str
    expires_at: float  # epoch seconds

    @property
    def is_expired(self) -> bool:
        return time.time() >= (self.expires_at - 30)  # refresh 30s before actual expiry


class KotakAuthenticator:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient):
        self._settings = settings
        self._http = http_client
        self._session: KotakSession | None = None

    async def get_session(self) -> KotakSession:
        if self._session is None or self._session.is_expired:
            self._session = await self._login()
        return self._session

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(KotakAuthError),
    )
    async def _login(self) -> KotakSession:
        s = self._settings
        totp_code = pyotp.TOTP(s.kotak_neo_totp_secret).now()

        # Step 1: password grant -> short-lived "view token"  [UNVERIFIED endpoint/shape]
        try:
            resp = await self._http.post(
                f"{s.kotak_neo_base_url}/login/1.0/login/v2/validate",
                json={
                    "mobileNumber": s.kotak_neo_mobile_number,
                    "password": s.kotak_neo_password,
                },
                headers={"Authorization": f"Bearer {s.kotak_neo_api_key}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            step1 = resp.json()
        except httpx.HTTPError as exc:
            raise KotakAuthError(f"Kotak Neo password-grant login failed: {exc}") from exc

        view_token = step1.get("token") or step1.get("data", {}).get("token")
        sid = step1.get("sid") or step1.get("data", {}).get("sid")
        if not view_token or not sid:
            raise KotakAuthError(f"Kotak Neo login response missing token/sid: {step1}")

        # Step 2: TOTP validation -> full session token  [UNVERIFIED endpoint/shape]
        try:
            resp = await self._http.post(
                f"{s.kotak_neo_base_url}/login/1.0/login/v2/validate/totp",
                json={"sid": sid, "totp": totp_code},
                headers={"Authorization": f"Bearer {view_token}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            step2 = resp.json()
        except httpx.HTTPError as exc:
            raise KotakAuthError(f"Kotak Neo TOTP validation failed: {exc}") from exc

        session_token = step2.get("sessionToken") or step2.get("data", {}).get("sessionToken")
        if not session_token:
            raise KotakAuthError(f"Kotak Neo TOTP response missing sessionToken: {step2}")

        return KotakSession(
            access_token=view_token,
            session_token=session_token,
            sid=sid,
            expires_at=time.time() + 8 * 3600,  # Kotak Neo sessions are typically day-long; verify actual TTL
        )
