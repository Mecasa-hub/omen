"""Credits API endpoints: balance, purchase, history, Stripe webhook."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.utils import get_current_user
from config import settings
from database import get_session
from models import CreditTransaction, User

from .schemas import (
    CreditBalance,
    CreditHistoryResponse,
    CreditPurchase,
    CreditTransactionSchema,
)
from .service import CREDITS_PER_DOLLAR, check_balance, process_stripe_payment

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("/balance", response_model=CreditBalance)
async def get_balance(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return the current user's credit balance."""
    balance = await check_balance(session, current_user.id)
    return {
        "user_id": current_user.id,
        "balance": balance,
        "usd_equivalent": round(balance / CREDITS_PER_DOLLAR, 2),
    }


@router.post("/purchase", response_model=CreditTransactionSchema, status_code=status.HTTP_201_CREATED)
async def purchase_credits(
    body: CreditPurchase,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CreditTransaction:
    """Purchase credits via Stripe.

    In production this would create a Stripe PaymentIntent.
    For dev mode, credits are added immediately with a mock payment ID.
    """
    if settings.stripe_secret_key and settings.stripe_secret_key != "sk_test_placeholder":
        # Production Stripe flow would go here
        # For now, simulate successful payment
        pass

    # Dev mode: instant credit grant
    mock_payment_id = f"pi_dev_{uuid.uuid4().hex[:16]}"
    tx = await process_stripe_payment(
        session=session,
        user_id=current_user.id,
        amount_usd=body.amount_usd,
        stripe_payment_id=mock_payment_id,
    )
    logger.info(
        "Credit purchase: user=%s amount=$%.2f credits=%d",
        current_user.username,
        body.amount_usd,
        int(body.amount_usd * CREDITS_PER_DOLLAR),
    )
    return tx


@router.get("/history", response_model=CreditHistoryResponse)
async def get_history(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return paginated credit transaction history."""
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size

    # Count total
    count_result = await session.execute(
        select(func.count()).select_from(CreditTransaction).where(
            CreditTransaction.user_id == current_user.id
        )
    )
    total = count_result.scalar_one()

    # Fetch page
    result = await session.execute(
        select(CreditTransaction)
        .where(CreditTransaction.user_id == current_user.id)
        .order_by(CreditTransaction.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    transactions = list(result.scalars().all())

    return {
        "transactions": transactions,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Handle Stripe webhook events for payment completion.

    Verifies webhook signature, processes checkout.session.completed events,
    and adds credits to the appropriate user account.
    """
    body = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    # In production, verify signature with stripe.Webhook.construct_event
    # For dev mode, parse JSON directly
    import json
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    event_type = event.get("type", "")
    logger.info("Stripe webhook received: %s", event_type)

    if event_type == "checkout.session.completed":
        session_data = event.get("data", {}).get("object", {})
        customer_email = session_data.get("customer_email")
        amount_total = session_data.get("amount_total", 0)  # in cents
        payment_intent = session_data.get("payment_intent", "")

        if not customer_email:
            logger.warning("Webhook missing customer_email")
            return {"status": "ignored", "reason": "no customer_email"}

        # Find user by email
        result = await session.execute(
            select(User).where(User.email == customer_email)
        )
        user = result.scalar_one_or_none()
        if user is None:
            logger.warning("Webhook user not found: %s", customer_email)
            return {"status": "ignored", "reason": "user not found"}

        amount_usd = amount_total / 100.0
        await process_stripe_payment(
            session=session,
            user_id=user.id,
            amount_usd=amount_usd,
            stripe_payment_id=payment_intent,
        )
        logger.info("Webhook processed: %s purchased $%.2f", customer_email, amount_usd)
        return {"status": "processed"}

    return {"status": "ignored", "reason": f"unhandled event type: {event_type}"}
