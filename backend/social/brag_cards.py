"""Brag Card Generator.

Auto-generates shareable "win cards" as SVG data for trades and
predictions. Users can share these on social media to showcase
their performance.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Prediction, PredictionStatus, Trade, TradeStatus

logger = logging.getLogger(__name__)

# Card color themes based on performance
THEMES = {
    "profit": {"bg": "#0a1a0a", "accent": "#00ff88", "text": "#e0ffe0", "emoji": "🔥"},
    "big_win": {"bg": "#0a0a1a", "accent": "#ffd700", "text": "#fffff0", "emoji": "👑"},
    "loss": {"bg": "#1a0a0a", "accent": "#ff4444", "text": "#ffe0e0", "emoji": "📉"},
    "neutral": {"bg": "#0a0a0a", "accent": "#8888ff", "text": "#e0e0ff", "emoji": "🔮"},
    "prediction": {"bg": "#0a0a1a", "accent": "#ff66ff", "text": "#ffe0ff", "emoji": "🎯"},
}


async def generate_trade_brag(
    session: AsyncSession,
    user_id: uuid.UUID,
    trade_id: uuid.UUID,
    custom_message: Optional[str] = None,
) -> dict:
    """Generate a brag card for a specific trade."""
    result = await session.execute(
        select(Trade).where(Trade.id == trade_id, Trade.user_id == user_id)
    )
    trade = result.scalar_one_or_none()

    if not trade:
        raise ValueError(f"Trade {trade_id} not found")

    pnl = trade.pnl_usd or 0.0
    pnl_pct = (pnl / trade.amount_usd * 100) if trade.amount_usd > 0 else 0

    # Select theme based on PnL
    if pnl > 50:
        theme = THEMES["big_win"]
    elif pnl > 0:
        theme = THEMES["profit"]
    elif pnl < 0:
        theme = THEMES["loss"]
    else:
        theme = THEMES["neutral"]

    stats = {
        "pnl_usd": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 1),
        "amount_usd": round(trade.amount_usd, 2),
        "side": trade.side.value,
        "market_id": trade.market_id[:30],
        "status": trade.status.value,
    }

    card_id = _generate_card_id(user_id, trade_id)
    share_text = _build_trade_share_text(stats, custom_message)
    svg = _render_trade_svg(stats, theme, share_text)

    return {
        "card_id": card_id,
        "svg_content": svg,
        "image_url": None,
        "share_text": share_text,
        "stats": stats,
        "created_at": datetime.now(timezone.utc),
    }


async def generate_prediction_brag(
    session: AsyncSession,
    user_id: uuid.UUID,
    prediction_id: uuid.UUID,
    custom_message: Optional[str] = None,
) -> dict:
    """Generate a brag card for a specific prediction."""
    result = await session.execute(
        select(Prediction).where(
            Prediction.id == prediction_id,
            Prediction.user_id == user_id,
        )
    )
    prediction = result.scalar_one_or_none()

    if not prediction:
        raise ValueError(f"Prediction {prediction_id} not found")

    theme = THEMES["prediction"]
    confidence_pct = round((prediction.confidence or 0) * 100, 1)

    stats = {
        "verdict": prediction.verdict or "N/A",
        "confidence": confidence_pct,
        "market_id": prediction.market_id[:30],
        "whale_alignment": round(prediction.whale_alignment or 0, 2),
        "agent_count": 5,  # Standard debate panel size
        "status": prediction.status.value,
    }

    card_id = _generate_card_id(user_id, prediction_id)
    share_text = _build_prediction_share_text(stats, custom_message)
    svg = _render_prediction_svg(stats, theme, share_text)

    return {
        "card_id": card_id,
        "svg_content": svg,
        "image_url": None,
        "share_text": share_text,
        "stats": stats,
        "created_at": datetime.now(timezone.utc),
    }


def _generate_card_id(user_id: uuid.UUID, content_id: uuid.UUID) -> str:
    """Generate a unique, URL-safe card ID."""
    raw = f"{user_id}:{content_id}:{datetime.now(timezone.utc).isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _build_trade_share_text(stats: dict, custom: Optional[str]) -> str:
    """Build share text for a trade brag."""
    pnl = stats["pnl_usd"]
    pnl_sign = "+" if pnl >= 0 else ""
    emoji = "🔥" if pnl > 0 else "📉" if pnl < 0 else "🔮"

    text = (
        f"{emoji} OMEN Trade Alert\n"
        f"{pnl_sign}${pnl:.2f} ({pnl_sign}{stats['pnl_pct']:.1f}%)\n"
        f"Side: {stats['side'].upper()} | Amount: ${stats['amount_usd']:.2f}\n"
    )
    if custom:
        text += f"\n{custom}\n"
    text += "\n🔮 Powered by OMEN — omen.market"
    return text


def _build_prediction_share_text(stats: dict, custom: Optional[str]) -> str:
    """Build share text for a prediction brag."""
    text = (
        f"🎯 OMEN Oracle Verdict\n"
        f"Verdict: {stats['verdict']} | Confidence: {stats['confidence']}%\n"
        f"Whale Alignment: {stats['whale_alignment']:+.2f}\n"
        f"AI Agents: {stats['agent_count']} debated\n"
    )
    if custom:
        text += f"\n{custom}\n"
    text += "\n🔮 Powered by OMEN — omen.market"
    return text


def _render_trade_svg(stats: dict, theme: dict, share_text: str) -> str:
    """Render a trade brag card as SVG."""
    pnl = stats["pnl_usd"]
    pnl_sign = "+" if pnl >= 0 else ""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{theme['bg']}"/>
      <stop offset="100%" style="stop-color:#111111"/>
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
  </defs>
  <rect width="600" height="400" rx="20" fill="url(#bg)" stroke="{theme['accent']}" stroke-width="2"/>
  <text x="30" y="50" fill="{theme['accent']}" font-family="monospace" font-size="24" font-weight="bold" filter="url(#glow)">OMEN {theme['emoji']}</text>
  <text x="30" y="85" fill="{theme['text']}" font-family="monospace" font-size="16" opacity="0.7">Trade Result</text>
  <line x1="30" y1="100" x2="570" y2="100" stroke="{theme['accent']}" stroke-width="1" opacity="0.3"/>
  <text x="300" y="180" fill="{theme['accent']}" font-family="monospace" font-size="56" font-weight="bold" text-anchor="middle" filter="url(#glow)">{pnl_sign}${pnl:.2f}</text>
  <text x="300" y="220" fill="{theme['text']}" font-family="monospace" font-size="24" text-anchor="middle">{pnl_sign}{stats['pnl_pct']:.1f}%</text>
  <text x="30" y="280" fill="{theme['text']}" font-family="monospace" font-size="14" opacity="0.8">Side: {stats['side'].upper()}</text>
  <text x="300" y="280" fill="{theme['text']}" font-family="monospace" font-size="14" opacity="0.8">Amount: ${stats['amount_usd']:.2f}</text>
  <text x="30" y="310" fill="{theme['text']}" font-family="monospace" font-size="12" opacity="0.5">Market: {stats['market_id']}</text>
  <line x1="30" y1="340" x2="570" y2="340" stroke="{theme['accent']}" stroke-width="1" opacity="0.3"/>
  <text x="300" y="375" fill="{theme['accent']}" font-family="monospace" font-size="14" text-anchor="middle" opacity="0.8">🔮 omen.market</text>
</svg>"""


def _render_prediction_svg(stats: dict, theme: dict, share_text: str) -> str:
    """Render a prediction brag card as SVG."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{theme['bg']}"/>
      <stop offset="100%" style="stop-color:#111111"/>
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
  </defs>
  <rect width="600" height="400" rx="20" fill="url(#bg)" stroke="{theme['accent']}" stroke-width="2"/>
  <text x="30" y="50" fill="{theme['accent']}" font-family="monospace" font-size="24" font-weight="bold" filter="url(#glow)">OMEN ORACLE {theme['emoji']}</text>
  <text x="30" y="85" fill="{theme['text']}" font-family="monospace" font-size="16" opacity="0.7">AI Prediction Verdict</text>
  <line x1="30" y1="100" x2="570" y2="100" stroke="{theme['accent']}" stroke-width="1" opacity="0.3"/>
  <text x="300" y="170" fill="{theme['accent']}" font-family="monospace" font-size="48" font-weight="bold" text-anchor="middle" filter="url(#glow)">{stats['verdict']}</text>
  <text x="300" y="220" fill="{theme['text']}" font-family="monospace" font-size="28" text-anchor="middle">{stats['confidence']}% Confidence</text>
  <text x="30" y="275" fill="{theme['text']}" font-family="monospace" font-size="14" opacity="0.8">🐋 Whale Alignment: {stats['whale_alignment']:+.2f}</text>
  <text x="30" y="305" fill="{theme['text']}" font-family="monospace" font-size="14" opacity="0.8">🤖 AI Agents: {stats['agent_count']} debated</text>
  <text x="30" y="335" fill="{theme['text']}" font-family="monospace" font-size="12" opacity="0.5">Market: {stats['market_id']}</text>
  <line x1="30" y1="355" x2="570" y2="355" stroke="{theme['accent']}" stroke-width="1" opacity="0.3"/>
  <text x="300" y="385" fill="{theme['accent']}" font-family="monospace" font-size="14" text-anchor="middle" opacity="0.8">🔮 omen.market</text>
</svg>"""
