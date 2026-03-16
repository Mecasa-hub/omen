"""Whale Alert X (Twitter) Bot.

Posts whale movement alerts to X/Twitter automatically.
Uses the X API v2 for posting tweets with rich formatting.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

X_API_BASE = "https://api.twitter.com/2"


def format_whale_alert(alert: dict) -> str:
    """Format a whale alert into a tweet-ready string.

    Args:
        alert: Whale alert dict from the tracker engine.

    Returns:
        Formatted tweet string within 280 chars.
    """
    alert_type = alert.get("alert_type", "movement")
    whale = alert.get("whale_address", "unknown")[:10]
    label = alert.get("whale_label", "")
    market = alert.get("market_id", "unknown")[:30]
    side = alert.get("side", "")
    size = alert.get("size_change", 0)
    price = alert.get("price", 0)
    value_usd = abs(size * price) if size and price else 0

    # Select emoji based on alert type
    emoji_map = {
        "new_position": "🐋📥",
        "increase": "🐋📈",
        "decrease": "🐋📉",
        "exit": "🐋🚪",
    }
    emoji = emoji_map.get(alert_type, "🐋")

    # Build display name
    display = f"{label} ({whale}...)" if label else f"{whale}..."

    # Format based on alert type
    if alert_type == "new_position":
        action = f"opened a NEW {side} position"
    elif alert_type == "increase":
        action = f"INCREASED {side} position"
    elif alert_type == "decrease":
        action = f"DECREASED {side} position"
    elif alert_type == "exit":
        action = f"EXITED position"
    else:
        action = f"moved on"

    tweet = (
        f"{emoji} WHALE ALERT\n\n"
        f"{display} {action}\n"
    )

    if value_usd > 0:
        tweet += f"💰 Value: ${value_usd:,.2f}\n"
    if price > 0:
        tweet += f"📊 Price: ${price:.2f}\n"

    tweet += f"🏪 Market: {market}\n"
    tweet += f"\n🔮 Track whales at omen.market\n"
    tweet += "#Polymarket #Prediction #Whale"

    # Ensure within 280 char limit
    if len(tweet) > 280:
        tweet = tweet[:277] + "..."

    return tweet


def format_prediction_tweet(prediction: dict) -> str:
    """Format a prediction verdict into a shareable tweet.

    Args:
        prediction: Prediction result dict.

    Returns:
        Formatted tweet string.
    """
    verdict = prediction.get("verdict", "N/A")
    confidence = prediction.get("confidence", 0)
    market = prediction.get("market_question", prediction.get("market_id", ""))[:80]
    whale_align = prediction.get("whale_alignment", 0)

    conf_pct = round(confidence * 100, 1) if confidence <= 1 else round(confidence, 1)

    # Emoji based on confidence
    if conf_pct >= 80:
        conf_emoji = "🔥"
    elif conf_pct >= 60:
        conf_emoji = "📊"
    else:
        conf_emoji = "🤔"

    tweet = (
        f"🔮 OMEN Oracle Verdict\n\n"
        f"❓ {market}\n\n"
        f"🎯 Verdict: {verdict}\n"
        f"{conf_emoji} Confidence: {conf_pct}%\n"
        f"🐋 Whale Alignment: {whale_align:+.2f}\n\n"
        f"5 AI agents debated. The Oracle has spoken.\n"
        f"\n🔮 omen.market\n"
        f"#OMEN #Polymarket #AI"
    )

    if len(tweet) > 280:
        tweet = tweet[:277] + "..."

    return tweet


async def post_tweet(text: str) -> Optional[dict]:
    """Post a tweet to X/Twitter via API v2.

    Returns:
        API response dict on success, None on failure.
    """
    bearer_token = settings.x_bearer_token
    if not bearer_token or bearer_token == "placeholder":
        logger.info("X bot disabled (no bearer token). Would post: %s", text[:100])
        return {"simulated": True, "text": text, "posted_at": datetime.now(timezone.utc).isoformat()}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{X_API_BASE}/tweets",
                json={"text": text},
                headers={
                    "Authorization": f"Bearer {bearer_token}",
                    "Content-Type": "application/json",
                },
            )

            if resp.status_code == 201:
                data = resp.json()
                tweet_id = data.get("data", {}).get("id")
                logger.info("Tweet posted successfully: id=%s", tweet_id)
                return data
            else:
                logger.error(
                    "Tweet failed: status=%d body=%s",
                    resp.status_code, resp.text[:200],
                )
                return None

    except Exception as exc:
        logger.error("X API error: %s", exc, exc_info=True)
        return None


async def post_whale_alert(alert: dict) -> Optional[dict]:
    """Format and post a whale alert to X/Twitter."""
    tweet = format_whale_alert(alert)
    logger.info("Posting whale alert: %s", tweet[:80])
    return await post_tweet(tweet)


async def post_prediction(prediction: dict) -> Optional[dict]:
    """Format and post a prediction verdict to X/Twitter."""
    tweet = format_prediction_tweet(prediction)
    logger.info("Posting prediction: %s", tweet[:80])
    return await post_tweet(tweet)


async def post_brag_card(share_text: str, card_url: Optional[str] = None) -> Optional[dict]:
    """Post a brag card share to X/Twitter.

    In production, would also attach the card image via media upload.
    """
    text = share_text
    if card_url:
        text += f"\n{card_url}"

    if len(text) > 280:
        text = text[:277] + "..."

    return await post_tweet(text)
