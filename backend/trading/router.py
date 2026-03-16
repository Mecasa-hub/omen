"""Trading API endpoints: execute, positions, history, copy-trading."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.utils import get_current_user
from credits.service import calculate_trade_fee, deduct_credits
from database import get_session
from models import Trade, TradeStatus, TransactionType, User

from .copy_engine import get_user_copy_sessions, start_copy_session, stop_copy_session
from .executor import cancel_order, place_order
from .risk_manager import check_risk_limits
from .schemas import (
    CopyTradeConfig,
    CopyTradeStatus,
    Position,
    TradeHistoryResponse,
    TradeRequest,
    TradeResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/trading", tags=["trading"])


@router.post("/execute", response_model=TradeResponse, status_code=status.HTTP_201_CREATED)
async def execute_trade(
    body: TradeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Trade:
    """Execute a trade on Polymarket.

    Runs risk checks, calculates and deducts the platform fee (1%),
    then places the order via the CLOB executor.
    """
    # Run risk checks
    risk = await check_risk_limits(
        session=session,
        user_id=current_user.id,
        market_id=body.market_id,
        amount_usd=body.amount_usd,
    )
    if not risk.passed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Risk check failed: {risk.reason}",
        )

    # Calculate and deduct platform fee (1% of trade amount)
    fee_usd = await calculate_trade_fee(body.amount_usd)
    fee_credits = max(1, int(fee_usd * 10))  # Convert to credits ($1 = 10 credits)

    try:
        await deduct_credits(
            session=session,
            user_id=current_user.id,
            amount=fee_credits,
            tx_type=TransactionType.TRADE_FEE,
            description=f"Trade fee: {fee_usd:.4f} USD on ${body.amount_usd:.2f} trade",
            metadata_json={"market_id": body.market_id, "trade_amount": body.amount_usd},
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_402_PAYMENT_REQUIRED:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Insufficient credits for trade fee ({fee_credits} credits)",
            ) from exc
        raise

    # Place the order
    trade = await place_order(
        session=session,
        user=current_user,
        market_id=body.market_id,
        token_id=body.token_id,
        side=body.side,
        amount_usd=body.amount_usd,
        price=body.price,
        prediction_id=body.prediction_id,
    )

    await session.commit()
    await session.refresh(trade)

    logger.info(
        "Trade executed: user=%s market=%s side=%s amount=$%.2f status=%s",
        current_user.username, body.market_id[:20], body.side, body.amount_usd, trade.status.value,
    )
    return trade


@router.get("/positions", response_model=list[Position])
async def get_positions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Trade]:
    """Get the current user's open positions (filled and partially filled trades)."""
    result = await session.execute(
        select(Trade)
        .where(
            Trade.user_id == current_user.id,
            Trade.status.in_([TradeStatus.FILLED, TradeStatus.PARTIALLY_FILLED]),
        )
        .order_by(Trade.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/history", response_model=TradeHistoryResponse)
async def get_trade_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    market_id: str | None = None,
    side: str | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get paginated trade history with optional filters."""
    base_query = select(Trade).where(Trade.user_id == current_user.id)
    count_query = select(func.count()).select_from(Trade).where(Trade.user_id == current_user.id)

    if market_id:
        base_query = base_query.where(Trade.market_id == market_id)
        count_query = count_query.where(Trade.market_id == market_id)
    if side:
        from models import TradeSide
        try:
            trade_side = TradeSide(side.lower())
            base_query = base_query.where(Trade.side == trade_side)
            count_query = count_query.where(Trade.side == trade_side)
        except ValueError:
            pass

    total = (await session.execute(count_query)).scalar_one()

    offset = (page - 1) * page_size
    result = await session.execute(
        base_query.order_by(Trade.created_at.desc()).offset(offset).limit(page_size)
    )
    trades = list(result.scalars().all())

    return {
        "trades": trades,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/cancel/{trade_id}", response_model=TradeResponse)
async def cancel_trade(
    trade_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Trade:
    """Cancel a pending or placed trade."""
    result = await session.execute(
        select(Trade).where(Trade.id == trade_id, Trade.user_id == current_user.id)
    )
    trade = result.scalar_one_or_none()

    if trade is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")

    if trade.status not in (TradeStatus.PENDING, TradeStatus.PLACED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel trade in {trade.status.value} state",
        )

    trade = await cancel_order(session, current_user, trade)
    await session.commit()
    return trade


@router.post("/copy/start", status_code=status.HTTP_200_OK)
async def start_copy(
    body: CopyTradeConfig,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Start copy-trading a whale wallet.

    Configures the copy engine to mirror the specified whale's positions
    with the user's risk settings.
    """
    return await start_copy_session(
        session=session,
        user=current_user,
        whale_address=body.whale_address,
        max_trade_usd=body.max_trade_usd,
        copy_percentage=body.copy_percentage,
        stop_loss_pct=body.stop_loss_pct,
        auto_exit=body.auto_exit,
        markets_whitelist=body.markets_whitelist,
        markets_blacklist=body.markets_blacklist,
    )


@router.post("/copy/stop", status_code=status.HTTP_200_OK)
async def stop_copy(
    whale_address: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Stop copy-trading a whale wallet."""
    return await stop_copy_session(
        user=current_user,
        whale_address=whale_address,
    )


@router.get("/copy/sessions", response_model=list[CopyTradeStatus])
async def list_copy_sessions(
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """List all active copy-trading sessions for the current user."""
    sessions = get_user_copy_sessions(current_user.id)
    return [
        {
            "whale_address": s["whale_address"],
            "is_active": s["is_active"],
            "config": {
                "whale_address": s["whale_address"],
                "max_trade_usd": s["max_trade_usd"],
                "copy_percentage": s["copy_percentage"],
                "stop_loss_pct": s["stop_loss_pct"],
                "auto_exit": s["auto_exit"],
            },
            "trades_executed": s["trades_executed"],
            "total_pnl_usd": s["total_pnl_usd"],
            "started_at": s["started_at"],
        }
        for s in sessions
    ]
