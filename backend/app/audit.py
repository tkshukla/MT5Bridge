import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_REDACT_KEYS = {"password", "totp", "secret", "token", "confirmation_token", "api_key"}


def _redact(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: ("***redacted***" if k.lower() in _REDACT_KEYS else v) for k, v in payload.items()}


async def record_audit_log(
    db: AsyncSession,
    *,
    actor: str,
    role: str,
    action: str,
    endpoint: str,
    request_meta: dict[str, Any],
    result: str,
    detail: str | None = None,
    source_ip: str | None = None,
) -> None:
    await db.execute(
        text(
            """
            INSERT INTO audit_logs (actor, role, action, endpoint, request_meta, result, detail, source_ip)
            VALUES (:actor, :role, :action, :endpoint, CAST(:request_meta AS JSONB), :result, :detail, :source_ip)
            """
        ),
        {
            "actor": actor,
            "role": role,
            "action": action,
            "endpoint": endpoint,
            "request_meta": json.dumps(_redact(request_meta)),
            "result": result,
            "detail": detail,
            "source_ip": source_ip,
        },
    )
    await db.commit()
