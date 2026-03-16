"""Whale Position-Delta Monitoring Engine.

Monitors tracked whale wallets for position changes by polling the
Polymarket API (or Polygon RPC). Detects new positions, increases,
decreases, and exits, generating alerts for each.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import WhalePosition, WhaleWallet

logger = logging.getLogger(__name__)

# Polymarket Gamma API base
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"


async def fetch_wallet_positions(address: str) -> list[dict]:
    """Fetch current positions for a wallet from Polymarket API.

    Queries the Polymarket Gamma API for the wallet's open positions.
    Falls back to synthetic data in dev mode.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Try Gamma API first
            resp = await client.get(
                f"{GAMMA_API}/positions",
                params={"user": address.lower(), "sizeThreshold": "0.01"},
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    logger.debug("Fetched %d positions for %s", len(data), address[:10])
                    return data
    except Exception as exc:
        logger.warning("Failed to fetch positions for %s: %s", address[:10], exc)

    # Dev fallback: return empty (no synthetic positions for tracker)
    return []


async def detect_position_changes(
    session: AsyncSession,
    wallet: WhaleWallet,
) -> list[dict]:
    """Compare current on-chain positions with stored positions.

    Returns a list of alert dicts for any detected changes:
    - new_position: whale entered a new market
    - increase: whale increased an existing position
    - decrease: whale decreased an existing position
    - exit: whale fully exited a position
    """
    alerts = []
    current_positions = await fetch_wallet_positions(wallet.address)

    # Build lookup of stored positions
    result = await session.execute(
        select(WhalePosition).where(
            WhalePosition.wallet_id == wallet.id,
            WhalePosition.is_open == True,
        )
    )
    stored = {p.market_id: p for p in result.scalars().all()}

    # Track which stored positions we've seen
    seen_markets = set()

    for pos_data in current_positions:
        market_id = pos_data.get("market", pos_data.get("conditionId", ""))
        if not market_id:
            continue

        seen_markets.add(market_id)
        size = float(pos_data.get("size", pos_data.get("currentValue", 0)))
        side = pos_data.get("outcome", pos_data.get("side", "YES")).upper()
        avg_price = float(pos_data.get("avgPrice", pos_data.get("price", 0.5)))
        current_price = float(pos_data.get("curPrice", pos_data.get("currentPrice", avg_price)))
        question = pos_data.get("title", pos_data.get("question", ""))
        token_id = pos_data.get("tokenId", pos_data.get("asset", market_id))

        if market_id in stored:
            # Existing position — check for changes
            old = stored[market_id]
            size_delta = size - old.size

            if abs(size_delta) > 0.01:
                alert_type = "increase" if size_delta > 0 else "decrease"
                alerts.append({
                    "alert_id": str(uuid.uuid4()),
                    "alert_type": alert_type,
                    "whale_address": wallet.address,
                    "whale_label": wallet.label,
                    "market_id": market_id,
                    "market_question": question,
                    "side": side,
                    "size_change": round(size_delta, 4),
                    "total_size": round(size, 4),
                    "price": current_price,
                    "timestamp": datetime.now(timezone.utc),
                })

                # Update stored position
                old.size = size
                old.current_price = current_price
                old.pnl_usd = round((current_price - old.avg_price) * size, 2)
                logger.info(
                    "Whale %s %s position in %s: %+.2f (total: %.2f)",
                    wallet.address[:10], alert_type, market_id[:20], size_delta, size,
                )
            else:
                # Just update current price
                old.current_price = current_price
                old.pnl_usd = round((current_price - old.avg_price) * size, 2)
        else:
            # New position
            new_pos = WhalePosition(
                wallet_id=wallet.id,
                market_id=market_id,
                market_question=question,
                token_id=token_id,
                side=side,
                size=size,
                avg_price=avg_price,
                current_price=current_price,
                pnl_usd=round((current_price - avg_price) * size, 2),
                is_open=True,
            )
            session.add(new_pos)

            alerts.append({
                "alert_id": str(uuid.uuid4()),
                "alert_type": "new_position",
                "whale_address": wallet.address,
                "whale_label": wallet.label,
                "market_id": market_id,
                "market_question": question,
                "side": side,
                "size_change": round(size, 4),
                "total_size": round(size, 4),
                "price": current_price,
                "timestamp": datetime.now(timezone.utc),
            })
            logger.info(
                "Whale %s NEW position: %s %s %.2f @ %.4f",
                wallet.address[:10], side, market_id[:20], size, avg_price,
            )

    # Detect exits: stored positions not seen in current data
    for market_id, old_pos in stored.items():
        if market_id not in seen_markets:
            old_pos.is_open = False
            old_pos.closed_at = datetime.now(timezone.utc)

            alerts.append({
                "alert_id": str(uuid.uuid4()),
                "alert_type": "exit",
                "whale_address": wallet.address,
                "whale_label": wallet.label,
                "market_id": market_id,
                "market_question": old_pos.market_question,
                "side": old_pos.side,
                "size_change": round(-old_pos.size, 4),
                "total_size": 0.0,
                "price": old_pos.current_price or old_pos.avg_price,
                "timestamp": datetime.now(timezone.utc),
            })
            logger.info(
                "Whale %s EXITED position: %s (was %.2f)",
                wallet.address[:10], market_id[:20], old_pos.size,
            )

    if alerts:
        await session.flush()

    return alerts


async def scan_all_whales(session: AsyncSession) -> list[dict]:
    """Scan all active whale wallets for position changes.

    Returns aggregated list of all alerts across all whales.
    """
    result = await session.execute(
        select(WhaleWallet).where(WhaleWallet.is_active == True)
    )
    wallets = result.scalars().all()

    all_alerts = []
    for wallet in wallets:
        try:
            alerts = await detect_position_changes(session, wallet)
            all_alerts.extend(alerts)

            # Update last activity timestamp if any changes detected
            if alerts:
                wallet.last_activity_at = datetime.now(timezone.utc)
        except Exception as exc:
            logger.error("Error scanning whale %s: %s", wallet.address[:10], exc, exc_info=True)

    if all_alerts:
        await session.commit()
        logger.info("Whale scan complete: %d alerts from %d wallets", len(all_alerts), len(wallets))
    else:
        logger.debug("Whale scan complete: no changes detected across %d wallets", len(wallets))

    return all_alerts
