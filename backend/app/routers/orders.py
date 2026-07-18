"""
Manual order endpoints — the only place in this codebase that calls
KotakClient.place_order / modify_order / cancel_order. See docs/SECURITY.md
"No automated execution" for why that property matters and how it's enforced.

Every endpoint here requires a confirmation_token that only the MT5 EA mints, and only
after a user clicks a confirmation dialog (see mql5/Include/MT5Bridge/BridgeClient.mqh).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record_audit_log
from app.confirmation import assert_confirmation_fresh, hash_confirmation_token
from app.db import get_db
from app.kotak.exceptions import KotakApiError
from app.metrics import ORDER_ACTIONS_TOTAL
from app.models import Order, Position, Symbol
from app.schemas.orders import ClosePositionRequest, ManualOrderRequest, ModifyOrderRequest, OrderOut
from app.security import Principal, Role, require_role

router = APIRouter(tags=["orders"])


async def _get_active_symbol(db: AsyncSession, symbol: str) -> Symbol:
    row = (await db.execute(select(Symbol).where(Symbol.symbol == symbol, Symbol.is_active.is_(True)))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown or inactive symbol: {symbol}")
    return row


def _validate_lot_size(quantity: int, lot_size: int) -> None:
    if quantity % lot_size != 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"quantity {quantity} is not a multiple of lot size {lot_size}",
        )


@router.post("/manual-order", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def manual_order(
    body: ManualOrderRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_role(Role.TRADER)),
) -> OrderOut:
    assert_confirmation_fresh(body.confirmed_at)
    symbol_row = await _get_active_symbol(db, body.symbol)
    _validate_lot_size(body.quantity, symbol_row.lot_size)

    order = Order(
        id=uuid.uuid4(),
        symbol=body.symbol,
        side=body.side,
        order_type=body.order_type,
        product=body.product,
        quantity=body.quantity,
        price=body.price,
        action="PLACE",
        status="PENDING",
        confirmation_token_hash=hash_confirmation_token(body.confirmation_token),
        confirmed_at=body.confirmed_at,
        placed_by=principal.subject,
    )
    db.add(order)
    try:
        await db.flush()  # surfaces the unique-token-hash violation before we call the broker
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="confirmation token already used",
        ) from exc

    kotak_client = request.app.state.kotak_client
    try:
        result = await kotak_client.place_order(
            symbol=body.symbol,
            side=body.side,
            quantity=body.quantity,
            order_type=body.order_type,
            product=body.product,
            price=body.price,
        )
        order.status = "PLACED"
        order.kotak_order_id = result.get("orderId") or result.get("data", {}).get("orderId")
        ORDER_ACTIONS_TOTAL.labels(action="place", result="success").inc()
        audit_result, audit_detail = "success", None
    except KotakApiError as exc:
        order.status = "REJECTED"
        order.reject_reason = str(exc)
        ORDER_ACTIONS_TOTAL.labels(action="place", result="rejected").inc()
        audit_result, audit_detail = "rejected", str(exc)

    await db.commit()
    await record_audit_log(
        db,
        actor=principal.subject,
        role=principal.role.value,
        action="manual_order",
        endpoint="/manual-order",
        request_meta=body.model_dump(mode="json"),
        result=audit_result,
        detail=audit_detail,
        source_ip=request.client.host if request.client else None,
    )

    if order.status == "REJECTED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=order.reject_reason)
    return OrderOut.model_validate(order, from_attributes=True)


@router.post("/modify-order", response_model=OrderOut)
async def modify_order(
    body: ModifyOrderRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_role(Role.TRADER)),
) -> OrderOut:
    assert_confirmation_fresh(body.confirmed_at)

    existing = (
        await db.execute(select(Order).where(Order.kotak_order_id == body.order_id))
    ).scalar_one_or_none()
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown order_id: {body.order_id}")

    token_hash = hash_confirmation_token(body.confirmation_token)
    already_used = (
        await db.execute(select(Order).where(Order.confirmation_token_hash == token_hash))
    ).scalar_one_or_none()
    if already_used is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="confirmation token already used")

    kotak_client = request.app.state.kotak_client
    try:
        await kotak_client.modify_order(kotak_order_id=body.order_id, quantity=body.quantity, price=body.price)
        result_status, reject_reason = "MODIFIED", None
        ORDER_ACTIONS_TOTAL.labels(action="modify", result="success").inc()
    except KotakApiError as exc:
        result_status, reject_reason = "REJECTED", str(exc)
        ORDER_ACTIONS_TOTAL.labels(action="modify", result="rejected").inc()

    modify_record = Order(
        id=uuid.uuid4(),
        kotak_order_id=body.order_id,
        symbol=existing.symbol,
        side=existing.side,
        order_type=existing.order_type,
        product=existing.product,
        quantity=body.quantity or existing.quantity,
        price=body.price if body.price is not None else existing.price,
        action="MODIFY",
        status=result_status,
        reject_reason=reject_reason,
        confirmation_token_hash=token_hash,
        confirmed_at=body.confirmed_at,
        placed_by=principal.subject,
    )
    db.add(modify_record)
    await db.commit()
    await record_audit_log(
        db,
        actor=principal.subject,
        role=principal.role.value,
        action="modify_order",
        endpoint="/modify-order",
        request_meta=body.model_dump(mode="json"),
        result="success" if result_status == "MODIFIED" else "rejected",
        detail=reject_reason,
        source_ip=request.client.host if request.client else None,
    )

    if result_status == "REJECTED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=reject_reason)
    return OrderOut.model_validate(modify_record, from_attributes=True)


@router.post("/close-position", response_model=OrderOut)
async def close_position(
    body: ClosePositionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_role(Role.TRADER)),
) -> OrderOut:
    assert_confirmation_fresh(body.confirmed_at)

    position = (
        await db.execute(select(Position).where(Position.symbol == body.symbol, Position.product == body.product))
    ).scalar_one_or_none()
    if position is None or position.quantity == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no open position for symbol/product")

    close_qty = body.quantity or abs(position.quantity)
    if close_qty > abs(position.quantity):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"close quantity {close_qty} exceeds open position size {abs(position.quantity)}",
        )
    side = "SELL" if position.quantity > 0 else "BUY"

    token_hash = hash_confirmation_token(body.confirmation_token)
    order = Order(
        id=uuid.uuid4(),
        symbol=body.symbol,
        side=side,
        order_type="MARKET",
        product=body.product,
        quantity=close_qty,
        action="CLOSE",
        status="PENDING",
        confirmation_token_hash=token_hash,
        confirmed_at=body.confirmed_at,
        placed_by=principal.subject,
    )
    db.add(order)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="confirmation token already used") from exc

    kotak_client = request.app.state.kotak_client
    try:
        result = await kotak_client.place_order(
            symbol=body.symbol,
            side=side,
            quantity=close_qty,
            order_type="MARKET",
            product=body.product,
            price=None,
        )
        order.status = "PLACED"
        order.kotak_order_id = result.get("orderId") or result.get("data", {}).get("orderId")
        ORDER_ACTIONS_TOTAL.labels(action="close", result="success").inc()
        audit_result, audit_detail = "success", None
    except KotakApiError as exc:
        order.status = "REJECTED"
        order.reject_reason = str(exc)
        ORDER_ACTIONS_TOTAL.labels(action="close", result="rejected").inc()
        audit_result, audit_detail = "rejected", str(exc)

    await db.commit()
    await record_audit_log(
        db,
        actor=principal.subject,
        role=principal.role.value,
        action="close_position",
        endpoint="/close-position",
        request_meta=body.model_dump(mode="json"),
        result=audit_result,
        detail=audit_detail,
        source_ip=request.client.host if request.client else None,
    )

    if order.status == "REJECTED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=order.reject_reason)
    return OrderOut.model_validate(order, from_attributes=True)
