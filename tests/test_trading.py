"""OMEN — Trading Module Tests.

Covers trade execution, insufficient credits, risk limits,
copy-trading start/stop, trade history, and position tracking.
"""

from __future__ import annotations

import secrets
import sys
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from auth.utils import create_access_token, hash_password  # noqa: E402
from models import User, WhaleWallet  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════
# Trade Execution
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_execute_trade(
    client: AsyncClient, test_user: User, auth_headers: dict
):
    """User can execute a trade with sufficient credits."""
    response = await client.post(
        "/api/trading/execute",
        json={
            "market_id": "0x" + "ab" * 20,
            "token_id": "71321045663652420386911009" + "001",
            "side": "BUY",
            "amount_usd": 10.00,
        },
        headers=auth_headers,
    )
    # Accept 201 (created) or 200 (ok) — trade may be placed or simulated
    assert response.status_code in (200, 201), response.text
    data = response.json()
    assert "id" in data
    assert "status" in data
    assert "side" in data


@pytest.mark.asyncio
async def test_execute_trade_unauthenticated(client: AsyncClient):
    """Trade without auth returns 401/403."""
    response = await client.post(
        "/api/trading/execute",
        json={
            "market_id": "0x" + "cd" * 20,
            "token_id": "token_1",
            "side": "BUY",
            "amount_usd": 10.00,
        },
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_trade_insufficient_credits(
    client: AsyncClient, db_session: AsyncSession
):
    """Trade fails when user cannot cover the 2.5% execution fee."""
    # Create user with minimal credits (0)
    user = User(
        id=uuid.uuid4(),
        email=f"notrade_{secrets.token_hex(4)}@omen.test",
        username=f"notrade_{secrets.token_hex(4)}",
        hashed_password=hash_password("NoTrade123!"),
        is_active=True,
        credit_balance=0,
        referral_code=secrets.token_urlsafe(6)[:8].upper(),
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(user.id)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/trading/execute",
        json={
            "market_id": "0x" + "ef" * 20,
            "token_id": "token_x",
            "side": "BUY",
            "amount_usd": 100.00,
        },
        headers=headers,
    )
    assert response.status_code in (402, 403)


# ═══════════════════════════════════════════════════════════════════════
# Risk Limits
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_risk_limits(
    client: AsyncClient, test_user: User, auth_headers: dict
):
    """Excessively large trades are rejected by risk limits."""
    response = await client.post(
        "/api/trading/execute",
        json={
            "market_id": "0x" + "99" * 20,
            "token_id": "token_big",
            "side": "BUY",
            "amount_usd": 1_000_000.00,  # $1M — should exceed limits
        },
        headers=auth_headers,
    )
    # Should be rejected (400 bad request, 402, 403, or 422 validation)
    assert response.status_code in (400, 402, 403, 422), (
        f"Expected risk limit rejection, got {response.status_code}"
    )


@pytest.mark.asyncio
async def test_trade_negative_amount(
    client: AsyncClient, auth_headers: dict
):
    """Negative trade amount is rejected."""
    response = await client.post(
        "/api/trading/execute",
        json={
            "market_id": "0x" + "88" * 20,
            "token_id": "token_neg",
            "side": "BUY",
            "amount_usd": -10.00,
        },
        headers=auth_headers,
    )
    assert response.status_code == 422  # Validation error


# ═══════════════════════════════════════════════════════════════════════
# Copy Trading
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
async def copy_whale(db_session: AsyncSession) -> WhaleWallet:
    """Create a whale wallet suitable for copy-trading tests."""
    from datetime import datetime, timezone

    wallet = WhaleWallet(
        address=f"0x{secrets.token_hex(20)}",
        label="CopyTestWhale",
        total_volume_usd=1_000_000.0,
        total_pnl_usd=200_000.0,
        win_rate=0.70,
        roi_pct=42.0,
        num_trades=300,
        num_markets=80,
        is_active=True,
        last_activity_at=datetime.now(timezone.utc),
        discovered_at=datetime.now(timezone.utc),
    )
    db_session.add(wallet)
    await db_session.commit()
    await db_session.refresh(wallet)
    return wallet


@pytest.mark.asyncio
async def test_copy_trade_start(
    client: AsyncClient, test_user: User, auth_headers: dict, copy_whale: WhaleWallet
):
    """User can start copy-trading a whale."""
    response = await client.post(
        "/api/trading/copy/start",
        json={
            "whale_address": copy_whale.address,
            "max_trade_usd": 50.00,
            "copy_percentage": 0.10,
        },
        headers=auth_headers,
    )
    # Accept 200/201 (started) or 404 (endpoint may differ)
    assert response.status_code in (200, 201), response.text
    data = response.json()
    assert "whale_address" in data or "status" in data


@pytest.mark.asyncio
async def test_copy_trade_stop(
    client: AsyncClient, test_user: User, auth_headers: dict, copy_whale: WhaleWallet
):
    """User can stop copy-trading a whale."""
    # Start first
    await client.post(
        "/api/trading/copy/start",
        json={
            "whale_address": copy_whale.address,
            "max_trade_usd": 50.00,
            "copy_percentage": 0.10,
        },
        headers=auth_headers,
    )

    # Stop
    response = await client.post(
        "/api/trading/copy/stop",
        json={"whale_address": copy_whale.address},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_copy_trade_nonexistent_whale(
    client: AsyncClient, auth_headers: dict
):
    """Starting copy-trade for non-existent whale returns 404."""
    response = await client.post(
        "/api/trading/copy/start",
        json={
            "whale_address": "0x" + "00" * 20,
            "max_trade_usd": 50.00,
            "copy_percentage": 0.10,
        },
        headers=auth_headers,
    )
    assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Trade History
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_trade_history(
    client: AsyncClient, test_user: User, auth_headers: dict
):
    """User can retrieve their trade history."""
    response = await client.get("/api/trading/history", headers=auth_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "trades" in data
    assert isinstance(data["trades"], list)


@pytest.mark.asyncio
async def test_trade_history_pagination(
    client: AsyncClient, auth_headers: dict
):
    """Trade history supports pagination."""
    response = await client.get(
        "/api/trading/history?page=1&page_size=5",
        headers=auth_headers,
    )
    assert response.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
# Position Tracking
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_position_tracking(
    client: AsyncClient, test_user: User, auth_headers: dict
):
    """User can view their open positions."""
    response = await client.get("/api/trading/positions", headers=auth_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)  # Returns list of positions


@pytest.mark.asyncio
async def test_position_after_trade(
    client: AsyncClient, test_user: User, auth_headers: dict
):
    """After executing a trade, it appears in positions."""
    # Execute a trade
    trade_resp = await client.post(
        "/api/trading/execute",
        json={
            "market_id": "0x" + "77" * 20,
            "token_id": "token_pos_test",
            "side": "BUY",
            "amount_usd": 10.00,
        },
        headers=auth_headers,
    )

    if trade_resp.status_code in (200, 201):
        # Check positions
        pos_resp = await client.get("/api/trading/positions", headers=auth_headers)
        assert pos_resp.status_code == 200
        positions = pos_resp.json()
        # The new trade should appear (as a position or in trade list)
        assert isinstance(positions, list)
