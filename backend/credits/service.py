"""Credit service — business logic for balance mutations.

All balance changes go through this layer so that the credit_transactions
ledger stays consistent with the user.credit_balance column.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import CreditTransaction, Referral, TransactionType, User

logger = logging.getLogger(__name__)

# Pricing constants
CREDITS_PER_DOLLAR = 10  # $5 = 50 credits
TRADE_FEE_PCT = 0.025  # 2.5%
WIN_FEE_PCT = 0.05  # 5% of profits
REFERRAL_BONUS_PCT = 0.10  # 10% of referee purchases


async def check_balance(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Return the current credit balance for a user."""
    result = await session.execute(
        select(User.credit_balance).where(User.id == user_id)
    )
    balance = result.scalar_one_or_none()
    if balance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return balance


async def add_credits(
    session: AsyncSession,
    user_id: uuid.UUID,
    amount: int,
    tx_type: TransactionType,
    description: Optional[str] = None,
    stripe_payment_id: Optional[str] = None,
    metadata_json: Optional[dict] = None,
) -> CreditTransaction:
    """Add credits to a user's balance and record the ledger entry.

    Uses SELECT FOR UPDATE to prevent race conditions on balance.
    """
    if amount <= 0:
        raise ValueError("Credit amount must be positive")

    # Lock row for update to prevent concurrent modification
    result = await session.execute(
        select(User).where(User.id == user_id).with_for_update()
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    new_balance = user.credit_balance + amount
    user.credit_balance = new_balance

    tx = CreditTransaction(
        user_id=user_id,
        tx_type=tx_type,
        amount=amount,
        balance_after=new_balance,
        description=description,
        stripe_payment_id=stripe_payment_id,
        metadata_json=metadata_json,
    )
    session.add(tx)
    await session.flush()

    logger.info("Credits +%d for user %s (type=%s, new_balance=%d)", amount, user_id, tx_type.value, new_balance)
    return tx


async def deduct_credits(
    session: AsyncSession,
    user_id: uuid.UUID,
    amount: int,
    tx_type: TransactionType,
    description: Optional[str] = None,
    metadata_json: Optional[dict] = None,
) -> CreditTransaction:
    """Deduct credits from a user's balance.

    Raises HTTPException 402 if insufficient balance.
    Uses SELECT FOR UPDATE to prevent race conditions.
    """
    if amount <= 0:
        raise ValueError("Deduction amount must be positive")

    result = await session.execute(
        select(User).where(User.id == user_id).with_for_update()
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.credit_balance < amount:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits: have {user.credit_balance}, need {amount}",
        )

    new_balance = user.credit_balance - amount
    user.credit_balance = new_balance

    tx = CreditTransaction(
        user_id=user_id,
        tx_type=tx_type,
        amount=-amount,
        balance_after=new_balance,
        description=description,
        metadata_json=metadata_json,
    )
    session.add(tx)
    await session.flush()

    logger.info("Credits -%d for user %s (type=%s, new_balance=%d)", amount, user_id, tx_type.value, new_balance)
    return tx


async def process_stripe_payment(
    session: AsyncSession,
    user_id: uuid.UUID,
    amount_usd: float,
    stripe_payment_id: str,
) -> CreditTransaction:
    """Process a successful Stripe payment: add credits and handle referral bonus.

    Conversion: $1 = 10 credits ($5 = 50 credits).
    If user was referred, referrer gets 10% of the purchase as bonus credits.
    """
    credits_to_add = int(amount_usd * CREDITS_PER_DOLLAR)

    # Add credits to purchaser
    tx = await add_credits(
        session=session,
        user_id=user_id,
        amount=credits_to_add,
        tx_type=TransactionType.PURCHASE,
        description=f"Purchase: ${amount_usd:.2f} = {credits_to_add} credits",
        stripe_payment_id=stripe_payment_id,
        metadata_json={"amount_usd": amount_usd, "rate": CREDITS_PER_DOLLAR},
    )

    # Handle referral bonus: 10% of purchase credits to referrer
    result = await session.execute(
        select(User.referred_by).where(User.id == user_id)
    )
    referred_by = result.scalar_one_or_none()

    if referred_by is not None:
        bonus = max(1, int(credits_to_add * REFERRAL_BONUS_PCT))
        await add_credits(
            session=session,
            user_id=referred_by,
            amount=bonus,
            tx_type=TransactionType.REFERRAL_BONUS,
            description=f"Referral bonus: {REFERRAL_BONUS_PCT*100:.0f}% of {credits_to_add} credits",
            metadata_json={"referee_id": str(user_id), "purchase_credits": credits_to_add},
        )

        # Update referral record
        await session.execute(
            update(Referral)
            .where(Referral.referee_id == user_id)
            .values(total_bonus_credits=Referral.total_bonus_credits + bonus)
        )
        logger.info("Referral bonus +%d credits to %s for referee %s purchase", bonus, referred_by, user_id)

    await session.commit()
    return tx


async def calculate_trade_fee(amount_usd: float) -> float:
    """Calculate the platform fee for a trade (2.5% of trade amount)."""
    return round(amount_usd * TRADE_FEE_PCT, 4)


async def calculate_win_fee(profit_usd: float) -> float:
    """Calculate the platform fee on profits (5% of profit)."""
    if profit_usd <= 0:
        return 0.0
    return round(profit_usd * WIN_FEE_PCT, 4)
