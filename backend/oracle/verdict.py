"""Consensus Calculation & Confidence Scoring.

Takes agent votes from the debate simulator, computes a weighted
consensus, cross-references whale positions, and produces a final
verdict with adjusted confidence.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import WhalePosition, WhaleWallet

logger = logging.getLogger(__name__)

# Persona weight overrides (matches debate_simulator AGENT_PERSONAS)
PERSONA_WEIGHTS = {
    "Atlas": 1.0,
    "Nemesis": 1.0,
    "Quant": 1.2,
    "Maverick": 0.8,
    "Clio": 0.9,
}

# How much whale alignment can shift the final confidence
WHALE_ALIGNMENT_FACTOR = 0.15


def calculate_consensus(agent_results: list[dict]) -> dict:
    """Calculate weighted consensus from agent votes.

    Each agent casts YES/NO with a confidence score and a weight.
    Consensus = weighted sum of (confidence * direction) / total_weight.

    Args:
        agent_results: List of dicts from debate_simulator, each with
                       'vote', 'confidence', 'weight', 'agent_name', etc.

    Returns:
        Dict with 'direction', 'confidence', 'vote_breakdown', 'reasoning_summary'.
    """
    if not agent_results:
        return {
            "direction": "YES",
            "confidence": 0.5,
            "vote_breakdown": [],
            "reasoning_summary": "No agents participated in the debate.",
        }

    weighted_yes = 0.0
    weighted_no = 0.0
    total_weight = 0.0
    vote_breakdown = []

    for agent in agent_results:
        name = agent.get("agent_name", "Unknown")
        vote = agent.get("vote", "YES").upper()
        confidence = float(agent.get("confidence", 0.5))
        weight = float(agent.get("weight", PERSONA_WEIGHTS.get(name, 1.0)))

        weighted_contribution = confidence * weight
        if vote == "YES":
            weighted_yes += weighted_contribution
        else:
            weighted_no += weighted_contribution

        total_weight += weight

        vote_breakdown.append({
            "agent_name": name,
            "persona": agent.get("persona", "unknown"),
            "vote": vote,
            "confidence": round(confidence, 3),
            "weight": round(weight, 2),
            "reasoning": agent.get("reasoning", ""),
        })

    # Calculate consensus direction and strength
    if total_weight == 0:
        direction = "YES"
        raw_confidence = 0.5
    else:
        yes_score = weighted_yes / total_weight
        no_score = weighted_no / total_weight
        direction = "YES" if yes_score >= no_score else "NO"
        # Confidence = how dominant the winning side is (0.5 to 1.0 mapped to 0.0 to 1.0)
        winning_score = max(yes_score, no_score)
        raw_confidence = min(0.95, max(0.1, winning_score))

    # Count votes
    yes_count = sum(1 for v in vote_breakdown if v["vote"] == "YES")
    no_count = len(vote_breakdown) - yes_count

    # Build reasoning summary
    reasoning_summary = (
        f"Consensus: {direction} with {raw_confidence:.1%} confidence. "
        f"Vote split: {yes_count} YES / {no_count} NO across {len(vote_breakdown)} agents. "
        f"Weighted YES score: {weighted_yes:.2f}, NO score: {weighted_no:.2f}."
    )

    return {
        "direction": direction,
        "confidence": round(raw_confidence, 3),
        "vote_breakdown": vote_breakdown,
        "yes_count": yes_count,
        "no_count": no_count,
        "weighted_yes": round(weighted_yes, 3),
        "weighted_no": round(weighted_no, 3),
        "reasoning_summary": reasoning_summary,
    }


async def get_whale_alignment(
    session: AsyncSession,
    market_id: str,
    direction: str,
) -> float:
    """Calculate whale alignment score for a market prediction.

    Checks what side tracked whales are on for this market and
    returns a score from -1.0 (whales disagree) to +1.0 (whales agree).

    Args:
        session: Database session.
        market_id: Polymarket market/condition ID.
        direction: The predicted direction (YES or NO).

    Returns:
        Alignment score: -1.0 to 1.0.
    """
    # Find whale positions in this market
    result = await session.execute(
        select(WhalePosition, WhaleWallet)
        .join(WhaleWallet, WhalePosition.wallet_id == WhaleWallet.id)
        .where(
            WhalePosition.market_id == market_id,
            WhalePosition.is_open == True,
        )
    )
    rows = result.all()

    if not rows:
        logger.debug("No whale positions found for market %s", market_id)
        return 0.0  # Neutral — no whale data

    # Calculate weighted alignment based on position size and whale ROI
    aligned_weight = 0.0
    opposed_weight = 0.0

    for position, wallet in rows:
        # Weight by position size and whale performance (ROI)
        size_weight = min(position.size, 10000.0) / 10000.0  # normalize
        roi_weight = max(0.1, min(2.0, 1.0 + (wallet.roi_pct / 100.0)))  # 0.1 to 2.0
        total_weight = size_weight * roi_weight

        # Determine if whale is on the same side as prediction
        whale_side = position.side.upper()
        prediction_side = direction.upper()

        if whale_side == prediction_side:
            aligned_weight += total_weight
        else:
            opposed_weight += total_weight

    total = aligned_weight + opposed_weight
    if total == 0:
        return 0.0

    # Score from -1 (all opposed) to +1 (all aligned)
    alignment = (aligned_weight - opposed_weight) / total
    logger.info(
        "Whale alignment for market %s direction %s: %.2f (%d positions)",
        market_id, direction, alignment, len(rows),
    )
    return round(alignment, 3)


def apply_whale_adjustment(
    base_confidence: float,
    whale_alignment: float,
) -> float:
    """Adjust prediction confidence based on whale alignment.

    Whale agreement boosts confidence; disagreement dampens it.
    The adjustment is bounded by WHALE_ALIGNMENT_FACTOR.

    Args:
        base_confidence: Raw confidence from agent consensus (0.0-1.0).
        whale_alignment: Whale alignment score (-1.0 to 1.0).

    Returns:
        Adjusted confidence clamped to [0.05, 0.98].
    """
    adjustment = whale_alignment * WHALE_ALIGNMENT_FACTOR
    adjusted = base_confidence + adjustment
    final = max(0.05, min(0.98, adjusted))

    logger.debug(
        "Confidence adjustment: %.3f + (%.3f * %.2f) = %.3f -> %.3f",
        base_confidence, whale_alignment, WHALE_ALIGNMENT_FACTOR, adjusted, final,
    )
    return round(final, 3)


async def build_full_verdict(
    agent_results: list[dict],
    session: AsyncSession,
    market_id: str,
) -> dict:
    """Build the complete verdict including whale alignment.

    This is the main entry point for producing a final prediction verdict.

    Args:
        agent_results: List of agent vote dicts from debate simulator.
        session: Database session for whale position lookup.
        market_id: Polymarket market ID for whale alignment.

    Returns:
        Complete verdict dict matching the Verdict schema.
    """
    consensus = calculate_consensus(agent_results)
    direction = consensus["direction"]
    base_confidence = consensus["confidence"]

    whale_alignment = await get_whale_alignment(session, market_id, direction)
    final_confidence = apply_whale_adjustment(base_confidence, whale_alignment)

    verdict = {
        "direction": direction,
        "confidence": base_confidence,
        "agent_votes": consensus["vote_breakdown"],
        "whale_alignment": whale_alignment,
        "final_confidence": final_confidence,
        "reasoning_summary": (
            f"{consensus['reasoning_summary']} "
            f"Whale alignment: {whale_alignment:+.2f} "
            f"(final confidence: {final_confidence:.1%})."
        ),
    }

    logger.info(
        "Verdict for market %s: %s @ %.1f%% confidence (whale adj: %+.2f -> %.1f%%)",
        market_id, direction, base_confidence * 100,
        whale_alignment, final_confidence * 100,
    )
    return verdict
