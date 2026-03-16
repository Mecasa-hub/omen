"""Polymarket CLOB Client — Order Execution Engine.

Handles placing, canceling, and querying orders on Polymarket's
Central Limit Order Book (CLOB) via their REST API.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import Trade, TradeSide, TradeStatus, User

logger = logging.getLogger(__name__)

# Polymarket CLOB API
CLOB_API = "https://clob.polymarket.com"


async def place_order(
    session: AsyncSession,
    user: User,
    market_id: str,
    token_id: str,
    side: str,
    amount_usd: float,
    price: Optional[float] = None,
    prediction_id: Optional[uuid.UUID] = None,
    is_copy_trade: bool = False,
    copy_source_wallet: Optional[str] = None,
) -> Trade:
    """Place an order on Polymarket's CLOB.

    In production, this would use the user's Polymarket API credentials
    to submit a signed order. In dev mode, simulates order placement.

    Args:
        session: Database session.
        user: User placing the trade.
        market_id: Market/condition ID.
        token_id: Outcome token ID.
        side: 'buy' or 'sell'.
        amount_usd: Trade amount in USD.
        price: Limit price (None for best available).
        prediction_id: Optional linked prediction.
        is_copy_trade: Whether this is a copy trade.
        copy_source_wallet: Source whale address if copy trade.

    Returns:
        Trade record with order status.
    """
    trade_side = TradeSide.BUY if side.lower() == "buy" else TradeSide.SELL

    # Calculate size from amount and price
    effective_price = price or 0.50  # Default mid-price for market orders
    size = round(amount_usd / effective_price, 4)

    # Calculate platform fee (1% of trade amount)
    fee_usd = round(amount_usd * 0.01, 4)

    # Create trade record
    trade = Trade(
        user_id=user.id,
        market_id=market_id,
        token_id=token_id,
        side=trade_side,
        amount_usd=amount_usd,
        price=effective_price,
        size=size,
        status=TradeStatus.PENDING,
        fee_usd=fee_usd,
        is_copy_trade=is_copy_trade,
        copy_source_wallet=copy_source_wallet,
        prediction_id=prediction_id,
    )
    session.add(trade)
    await session.flush()

    # Attempt to place on Polymarket
    if _has_polymarket_credentials(user):
        try:
            order_result = await _submit_clob_order(
                user=user,
                token_id=token_id,
                side=side,
                size=size,
                price=effective_price,
            )
            trade.order_id = order_result.get("orderID", order_result.get("id"))
            trade.status = TradeStatus.PLACED
            logger.info(
                "Order placed: user=%s market=%s side=%s amount=$%.2f order_id=%s",
                user.username, market_id[:20], side, amount_usd, trade.order_id,
            )
        except Exception as exc:
            trade.status = TradeStatus.FAILED
            logger.error("Order placement failed: %s", exc, exc_info=True)
    else:
        # Dev mode: simulate successful placement
        trade.order_id = f"sim_{uuid.uuid4().hex[:12]}"
        trade.status = TradeStatus.FILLED
        logger.info(
            "Simulated order filled: user=%s market=%s side=%s amount=$%.2f",
            user.username, market_id[:20], side, amount_usd,
        )

    await session.flush()
    return trade


async def cancel_order(
    session: AsyncSession,
    user: User,
    trade: Trade,
) -> Trade:
    """Cancel a pending/placed order on Polymarket."""
    if trade.status not in (TradeStatus.PENDING, TradeStatus.PLACED):
        logger.warning("Cannot cancel trade %s in status %s", trade.id, trade.status)
        return trade

    if _has_polymarket_credentials(user) and trade.order_id:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.delete(
                    f"{CLOB_API}/order/{trade.order_id}",
                    headers=_build_auth_headers(user),
                )
                if resp.status_code in (200, 204):
                    trade.status = TradeStatus.CANCELLED
                    logger.info("Order cancelled: %s", trade.order_id)
                else:
                    logger.warning("Cancel failed with status %d", resp.status_code)
        except Exception as exc:
            logger.error("Cancel request failed: %s", exc)
    else:
        trade.status = TradeStatus.CANCELLED

    await session.flush()
    return trade


async def get_positions(
    user: User,
) -> list[dict]:
    """Fetch user's current open positions from Polymarket.

    Falls back to returning empty list in dev mode.
    """
    if not _has_polymarket_credentials(user):
        return []

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{CLOB_API}/positions",
                headers=_build_auth_headers(user),
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception as exc:
        logger.error("Failed to fetch positions: %s", exc)

    return []


async def _submit_clob_order(
    user: User,
    token_id: str,
    side: str,
    size: float,
    price: float,
) -> dict:
    """Submit a signed order to Polymarket CLOB API."""
    order_payload = {
        "tokenID": token_id,
        "side": side.upper(),
        "size": str(size),
        "price": str(price),
        "type": "GTC",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{CLOB_API}/order",
            json=order_payload,
            headers=_build_auth_headers(user),
        )
        resp.raise_for_status()
        return resp.json()


def _has_polymarket_credentials(user: User) -> bool:
    """Check if user has configured Polymarket API credentials."""
    return bool(
        user.polymarket_api_key
        and user.polymarket_api_secret
        and user.polymarket_api_key != "placeholder"
    )


def _build_auth_headers(user: User) -> dict:
    """Build authentication headers for Polymarket API calls."""
    return {
        "POLY-ADDRESS": user.polymarket_api_key or "",
        "POLY-SIGNATURE": user.polymarket_api_secret or "",
        "POLY-TIMESTAMP": str(int(datetime.now(timezone.utc).timestamp())),
        "POLY-PASSPHRASE": user.polymarket_passphrase or "",
        "Content-Type": "application/json",
    }
