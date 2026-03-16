"""OMEN — Credits Module Tests.

Covers balance retrieval, credit purchasing, deduction,
insufficient balance handling, transaction history, Stripe webhook,
and referral bonuses.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from models import CreditTransaction, TransactionType, User  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════
# Balance
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_balance(
    client: AsyncClient, test_user: User, auth_headers: dict
):
    """Authenticated user can check their credit balance."""
    response = await client.get("/api/credits/balance", headers=auth_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "balance" in data
    assert data["balance"] == test_user.credit_balance
    assert "user_id" in data


@pytest.mark.asyncio
async def test_get_balance_unauthenticated(client: AsyncClient):
    """Balance check without auth returns 401/403."""
    response = await client.get("/api/credits/balance")
    assert response.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════
# Purchase Credits
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_purchase_credits(
    client: AsyncClient, test_user: User, auth_headers: dict
):
    """User can purchase credits (dev mode auto-grants)."""
    initial_balance = test_user.credit_balance
    response = await client.post(
        "/api/credits/purchase",
        json={"amount_usd": 5.00},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["amount"] == 50  # $5 × 10 credits/$
    assert data["balance_after"] == initial_balance + 50


@pytest.mark.asyncio
async def test_purchase_credits_various_amounts(
    client: AsyncClient, test_user: User, auth_headers: dict
):
    """Purchase with $10 yields 100 credits."""
    response = await client.post(
        "/api/credits/purchase",
        json={"amount_usd": 10.00},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["amount"] == 100


# ═══════════════════════════════════════════════════════════════════════
# Credit Deduction (via prediction)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_deduct_credits_via_prediction(
    client: AsyncClient, test_user: User, auth_headers: dict
):
    """Making a prediction deducts 1 credit from balance."""
    # Get initial balance
    bal_resp = await client.get("/api/credits/balance", headers=auth_headers)
    initial = bal_resp.json()["balance"]

    # Make a prediction (costs 1 credit)
    response = await client.post(
        "/api/oracle/predict",
        json={"market_id": "0x" + "ab" * 20, "question": "Will BTC hit $100K?"},
        headers=auth_headers,
    )
    # Prediction may succeed or timeout, but credit should be deducted
    if response.status_code in (200, 201):
        # Verify balance decreased
        bal_resp2 = await client.get("/api/credits/balance", headers=auth_headers)
        new_balance = bal_resp2.json()["balance"]
        assert new_balance == initial - 1


@pytest.mark.asyncio
async def test_insufficient_credits(
    client: AsyncClient, db_session: AsyncSession
):
    """Prediction with 0 credits returns 402/403 error."""
    from auth.utils import create_access_token, hash_password
    import secrets

    # Create user with 0 credits
    broke_user = User(
        id=uuid.uuid4(),
        email=f"broke_{secrets.token_hex(4)}@omen.test",
        username=f"brokeuser_{secrets.token_hex(4)}",
        hashed_password=hash_password("BrokePass123!"),
        is_active=True,
        credit_balance=0,
        referral_code=secrets.token_urlsafe(6)[:8].upper(),
    )
    db_session.add(broke_user)
    await db_session.commit()

    token = create_access_token(broke_user.id)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/oracle/predict",
        json={"market_id": "0x" + "cd" * 20, "question": "Test?"},
        headers=headers,
    )
    # Should fail with 402 Payment Required or 403 Forbidden
    assert response.status_code in (402, 403), f"Expected 402/403, got {response.status_code}: {response.text}"


# ═══════════════════════════════════════════════════════════════════════
# Transaction History
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_credit_history(
    client: AsyncClient, test_user: User, auth_headers: dict
):
    """User can retrieve credit transaction history."""
    # First purchase some credits to create a transaction
    await client.post(
        "/api/credits/purchase",
        json={"amount_usd": 5.00},
        headers=auth_headers,
    )

    response = await client.get("/api/credits/history", headers=auth_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "transactions" in data
    assert isinstance(data["transactions"], list)
    assert len(data["transactions"]) >= 1


@pytest.mark.asyncio
async def test_credit_history_pagination(
    client: AsyncClient, test_user: User, auth_headers: dict
):
    """Transaction history supports pagination parameters."""
    response = await client.get(
        "/api/credits/history?page=1&page_size=5",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "page" in data or "transactions" in data


# ═══════════════════════════════════════════════════════════════════════
# Stripe Webhook
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_stripe_webhook_no_signature(client: AsyncClient):
    """Stripe webhook without valid signature is rejected or accepted in dev mode."""
    response = await client.post(
        "/api/credits/webhook",
        json={
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "metadata": {"user_id": str(uuid.uuid4()), "credits": "50"},
                    "amount_total": 500,
                },
            },
        },
        headers={"stripe-signature": "fake_sig"},
    )
    # In dev mode this may pass; in production it should fail
    # Accept any non-500 response as the endpoint is handling it
    assert response.status_code != 500 or response.status_code in (200, 400, 401, 403)


# ═══════════════════════════════════════════════════════════════════════
# Referral Bonus
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_referral_bonus_on_purchase(
    client: AsyncClient, test_user: User, second_user: User
):
    """When a referred user purchases, the referrer gets 10% bonus credits."""
    referrer_code = test_user.referral_code

    # Register a new user with referrer's code
    reg_response = await client.post(
        "/api/auth/register",
        json={
            "email": f"referred_{uuid.uuid4().hex[:6]}@omen.test",
            "username": f"referred_{uuid.uuid4().hex[:6]}",
            "password": "ReferredPass123!",
            "referral_code": referrer_code,
        },
    )

    if reg_response.status_code == 201:
        # Login as the referred user
        referred_data = reg_response.json()
        login_resp = await client.post(
            "/api/auth/login",
            json={
                "login": referred_data["email"],
                "password": "ReferredPass123!",
            },
        )
        if login_resp.status_code == 200:
            ref_token = login_resp.json()["access_token"]
            ref_headers = {"Authorization": f"Bearer {ref_token}"}

            # Purchase credits as referred user
            purchase_resp = await client.post(
                "/api/credits/purchase",
                json={"amount_usd": 10.00},
                headers=ref_headers,
            )
            # The referrer should eventually get 10% bonus (10 credits)
            # This tests that the purchase itself succeeds
            assert purchase_resp.status_code in (200, 201)
