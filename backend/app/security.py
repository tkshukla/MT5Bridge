import hashlib
from datetime import datetime, timedelta, timezone
from enum import Enum

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import get_settings

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class Role(str, Enum):
    VIEWER = "viewer"
    TRADER = "trader"
    ADMIN = "admin"


_ROLE_RANK = {Role.VIEWER: 0, Role.TRADER: 1, Role.ADMIN: 2}


class Principal(BaseModel):
    subject: str
    role: Role


def create_access_token(subject: str, role: Role) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_ttl_minutes)
    payload = {"sub": subject, "role": role.value, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str, role: Role) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_ttl_days)
    payload = {"sub": subject, "role": role.value, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Principal:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token") from exc
    return Principal(subject=payload["sub"], role=Role(payload["role"]))


# API keys are provisioned out-of-band (e.g. for Prometheus) and stored hashed.
# Populate via an admin script; this module only verifies.
def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


async def get_current_principal(
    token: str | None = Depends(oauth2_scheme),
    api_key: str | None = Security(api_key_header),
) -> Principal:
    if token:
        return decode_token(token)
    if api_key:
        # Service accounts (e.g. metrics scraping) get a fixed viewer-scope principal.
        # Real deployments should look up the hashed key against a table of issued keys;
        # kept minimal here since only /metrics currently uses this path.
        from app.db import async_session_factory  # local import avoids circular import at module load

        async with async_session_factory() as session:
            from sqlalchemy import text

            row = (
                await session.execute(
                    text("SELECT label, role FROM api_keys WHERE key_hash = :h AND revoked_at IS NULL"),
                    {"h": hash_api_key(api_key)},
                )
            ).first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")
        return Principal(subject=f"apikey:{row.label}", role=Role(row.role))
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing credentials")


def require_role(minimum: Role):
    async def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if _ROLE_RANK[principal.role] < _ROLE_RANK[minimum]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient role")
        return principal

    return dependency
