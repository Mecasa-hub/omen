"""Referral System.

Generate referral codes, track signups, and award bonus credits
for successful referrals. Referrers earn 10% of referee's credit purchases.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import (
    CreditTransaction,
    Referral,
    ReferralStatus,
    TransactionType,
    User,
)

logger = logging.getLogger(__name__)

REFERRAL_BONUS_RATE = 0.10  # 10% of referee's credit purchases
BASE_REFERRAL_URL = "https://omen.market/ref"


def generate_referral_code(user_id: uuid.UUID, username: str) -> str:
    """Generate a unique referral code for a user.

    Uses a hash of user_id + username truncated to 8 chars,
    prefixed with 'OMEN-' for branding.
    """
    raw = f"{user_id}:{username}:{settings.jwt_secret_key[:8]}"
    code_hash = hashlib.sha256(raw.encode()).hexdigest()[:8].upper()
    return f"OMEN-{code_hash}"


async def get_or_create_referral_code(
    session: AsyncSession,
    user: User,
) -> dict:
    """Get existing referral code or create one for the user."""
    if user.referral_code:
        return {
            "code": user.referral_code,
            "referral_url": f"{BASE_REFERRAL_URL}/{user.referral_code}",
            "created_at": user.created_at,
        }

    # Generate and save new code
    code = generate_referral_code(user.id, user.username)
    user.referral_code = code
    await session.flush()

    logger.info("Referral code created: user=%s code=%s", user.username, code)

    return {
        "code": code,
        "referral_url": f"{BASE_REFERRAL_URL}/{code}",
        "created_at": user.created_at,
    }


async def apply_referral_code(
    session: AsyncSession,
    referee: User,
    referral_code: str,
) -> Optional[dict]:
    """Apply a referral code during user signup.

    Links the new user (referee) to the referrer and creates
    a referral tracking record.
    """
    # Find referrer by code
    result = await session.execute(
        select(User).where(User.referral_code == referral_code.upper())
    )
    referrer = result.scalar_one_or_none()

    if not referrer:
        logger.warning("Invalid referral code: %s", referral_code)
        return None

    if referrer.id == referee.id:
        logger.warning("Self-referral attempted: user=%s", referee.username)
        return None

    # Check if already referred
    existing = await session.execute(
        select(Referral).where(Referral.referee_id == referee.id)
    )
    if existing.scalar_one_or_none():
        logger.warning("User %s already has a referral", referee.username)
        return None

    # Create referral record
    referral = Referral(
        referrer_id=referrer.id,
        referee_id=referee.id,
        referral_code=referral_code.upper(),
        status=ReferralStatus.ACTIVE,
    )
    session.add(referral)

    # Update referee's referred_by field
    referee.referred_by = referrer.id
    await session.flush()

    logger.info(
        "Referral applied: referrer=%s referee=%s code=%s",
        referrer.username, referee.username, referral_code,
    )

    return {
        "referrer": referrer.username,
        "referee": referee.username,
        "code": referral_code,
    }


async def award_referral_bonus(
    session: AsyncSession,
    referee_id: uuid.UUID,
    purchase_credits: int,
) -> Optional[int]:
    """Award referral bonus to the referrer when referee purchases credits.

    The referrer earns 10% of the referee's credit purchase.

    Returns:
        Number of bonus credits awarded, or None if no referral.
    """
    # Find the referral relationship
    result = await session.execute(
        select(Referral).where(
            Referral.referee_id == referee_id,
            Referral.status == ReferralStatus.ACTIVE,
        )
    )
    referral = result.scalar_one_or_none()

    if not referral:
        return None

    # Calculate bonus (10% of purchase)
    bonus_credits = max(1, int(purchase_credits * REFERRAL_BONUS_RATE))

    # Award credits to referrer
    tx = CreditTransaction(
        user_id=referral.referrer_id,
        amount=bonus_credits,
        tx_type=TransactionType.REFERRAL_BONUS,
        description=f"Referral bonus: 10% of {purchase_credits} credits from referee",
        metadata_json={"referee_id": str(referee_id), "purchase_credits": purchase_credits},
    )
    session.add(tx)

    # Update referral earnings
    referral.total_earned_credits += bonus_credits
    await session.flush()

    # Update referrer's credit balance
    referrer_result = await session.execute(
        select(User).where(User.id == referral.referrer_id)
    )
    referrer = referrer_result.scalar_one_or_none()
    if referrer:
        referrer.credit_balance += bonus_credits

    await session.flush()

    logger.info(
        "Referral bonus awarded: referrer_id=%s bonus=%d credits",
        referral.referrer_id, bonus_credits,
    )

    return bonus_credits


async def get_referral_stats(
    session: AsyncSession,
    user: User,
) -> dict:
    """Get comprehensive referral statistics for a user."""
    code = user.referral_code or "(none)"

    # Count referrals
    count_result = await session.execute(
        select(func.count()).select_from(Referral).where(
            Referral.referrer_id == user.id
        )
    )
    total_signups = count_result.scalar_one()

    # Total earnings
    earnings_result = await session.execute(
        select(func.coalesce(func.sum(Referral.total_earned_credits), 0)).where(
            Referral.referrer_id == user.id
        )
    )
    total_credits = int(earnings_result.scalar_one())
    total_usd = total_credits * 0.10  # $0.10 per credit

    # Recent referrals with referee usernames
    recent_result = await session.execute(
        select(Referral, User)
        .join(User, User.id == Referral.referee_id)
        .where(Referral.referrer_id == user.id)
        .order_by(Referral.created_at.desc())
        .limit(20)
    )
    recent = [
        {
            "referee_username": ref_user.username,
            "signed_up_at": referral.created_at,
            "credits_earned": referral.total_earned_credits,
        }
        for referral, ref_user in recent_result.all()
    ]

    return {
        "referral_code": code,
        "total_signups": total_signups,
        "total_earnings_credits": total_credits,
        "total_earnings_usd": round(total_usd, 2),
        "recent_referrals": recent,
    }
