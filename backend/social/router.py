"""Social API endpoints: share, referrals, brag cards, X bot."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.utils import get_current_user
from database import get_session
from models import User

from .brag_cards import generate_prediction_brag, generate_trade_brag
from .referral import get_or_create_referral_code, get_referral_stats
from .schemas import (
    BragCardData,
    BragRequest,
    ReferralCode,
    ReferralStats,
    ShareRequest,
    ShareResponse,
)
from .twitter_bot import post_brag_card, post_whale_alert

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/social", tags=["social"])


@router.post("/share", response_model=ShareResponse)
async def share_content(
    body: ShareRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Share a prediction or trade to a social platform.

    Generates a shareable link and optionally posts to X/Twitter.
    """
    # Build shareable URL
    base_url = "https://omen.market"
    share_url = f"{base_url}/{body.content_type}/{body.content_id}"

    # If sharing to Twitter, attempt to post
    if body.platform == "twitter":
        share_text = body.message or f"Check out my {body.content_type} on OMEN! 🔮"
        share_text += f"\n{share_url}"
        if len(share_text) > 280:
            share_text = share_text[:277] + "..."

        result = await post_brag_card(share_text)
        if result:
            logger.info(
                "Shared to Twitter: user=%s type=%s id=%s",
                current_user.username, body.content_type, body.content_id,
            )

    return {
        "share_url": share_url,
        "platform": body.platform,
        "content_type": body.content_type,
        "shared_at": datetime.now(timezone.utc),
    }


@router.get("/referral/code", response_model=ReferralCode)
async def get_referral_code(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get or create a referral code for the current user."""
    return await get_or_create_referral_code(session, current_user)


@router.get("/referral/stats", response_model=ReferralStats)
async def get_referral_statistics(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get referral program statistics for the current user.

    Shows total signups, earnings, and recent referral activity.
    """
    return await get_referral_stats(session, current_user)


@router.post("/brag", response_model=BragCardData)
async def generate_brag_card(
    body: BragRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Generate a shareable brag card for a trade or prediction.

    Creates an SVG card with the trade/prediction stats
    that can be shared on social media.
    """
    if not body.trade_id and not body.prediction_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either trade_id or prediction_id is required",
        )

    try:
        if body.trade_id:
            card = await generate_trade_brag(
                session=session,
                user_id=current_user.id,
                trade_id=body.trade_id,
                custom_message=body.custom_message,
            )
        else:
            card = await generate_prediction_brag(
                session=session,
                user_id=current_user.id,
                prediction_id=body.prediction_id,
                custom_message=body.custom_message,
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    logger.info(
        "Brag card generated: user=%s card=%s",
        current_user.username, card["card_id"],
    )
    return card


@router.post("/brag/share")
async def share_brag_to_twitter(
    body: BragRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Generate a brag card AND share it to X/Twitter in one step."""
    # Generate the card first
    if not body.trade_id and not body.prediction_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either trade_id or prediction_id is required",
        )

    try:
        if body.trade_id:
            card = await generate_trade_brag(
                session=session,
                user_id=current_user.id,
                trade_id=body.trade_id,
                custom_message=body.custom_message,
            )
        else:
            card = await generate_prediction_brag(
                session=session,
                user_id=current_user.id,
                prediction_id=body.prediction_id,
                custom_message=body.custom_message,
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    # Post to Twitter
    tweet_result = await post_brag_card(
        share_text=card["share_text"],
        card_url=card.get("image_url"),
    )

    return {
        "card": card,
        "tweet_posted": tweet_result is not None,
        "tweet_result": tweet_result,
    }
