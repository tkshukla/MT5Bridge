"""
Daily Kotak Neo login. TOTP and MPIN are dynamic — supplied fresh here each session,
never stored (see kotak/auth.py). Call this once each morning (or whenever the backend
restarts) before the read endpoints / order endpoints will work against live data.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.kotak.exceptions import KotakAuthError
from app.security import Principal, Role, require_role

router = APIRouter(tags=["auth"])


class KotakLoginRequest(BaseModel):
    totp: str = Field(min_length=6, max_length=6)
    mpin: str = Field(min_length=4, max_length=6)


class KotakLoginResponse(BaseModel):
    ucc: str
    greeting_name: str | None = None


@router.post("/auth/kotak-login", response_model=KotakLoginResponse)
async def kotak_login(
    body: KotakLoginRequest,
    request: Request,
    _principal: Principal = Depends(require_role(Role.ADMIN)),
) -> KotakLoginResponse:
    session_manager = request.app.state.kotak_session_manager
    try:
        result = await session_manager.login(totp=body.totp, mpin=body.mpin)
    except KotakAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return KotakLoginResponse(**result)
