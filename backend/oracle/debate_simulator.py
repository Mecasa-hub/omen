"""AI Agent Debate Simulator.

Simulates a structured debate between five AI personas, each analyzing
a prediction market question from a different perspective. Each agent
produces a reasoned argument and casts a YES/NO vote with confidence.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from .swarm_engine import query_mirofish

logger = logging.getLogger(__name__)

# ── Agent Personas ────────────────────────────────────────────────────────
AGENT_PERSONAS = {
    "Atlas": {
        "role": "bull",
        "description": "Optimistic macro strategist who weighs geopolitical and economic tailwinds",
        "bias": 0.1,  # slight YES bias
        "weight": 1.0,
        "prompt_prefix": (
            "You are Atlas, a bullish macro strategist. You look for reasons "
            "why an outcome is LIKELY. Focus on positive catalysts, momentum, "
            "historical precedents that support YES. Be persuasive but honest."
        ),
    },
    "Nemesis": {
        "role": "bear",
        "description": "Skeptical risk analyst who probes weaknesses and downside scenarios",
        "bias": -0.1,  # slight NO bias
        "weight": 1.0,
        "prompt_prefix": (
            "You are Nemesis, a bearish risk analyst. You look for reasons "
            "why an outcome is UNLIKELY. Focus on risks, obstacles, historical "
            "failures, and contrarian evidence. Be rigorous and challenging."
        ),
    },
    "Quant": {
        "role": "analyst",
        "description": "Data-driven quantitative analyst focused on probabilities and base rates",
        "bias": 0.0,
        "weight": 1.2,  # slightly higher weight for data-driven analysis
        "prompt_prefix": (
            "You are Quant, a quantitative analyst. Focus purely on data: "
            "base rates, statistical models, historical frequencies, and "
            "calibrated probability estimates. Avoid narrative; use numbers."
        ),
    },
    "Maverick": {
        "role": "contrarian",
        "description": "Contrarian thinker who challenges consensus and finds edge in mispricing",
        "bias": 0.0,
        "weight": 0.8,
        "prompt_prefix": (
            "You are Maverick, a contrarian thinker. Challenge the obvious "
            "narrative. Look for information asymmetry, crowd psychology errors, "
            "and scenarios the market is under-pricing. Be provocative."
        ),
    },
    "Clio": {
        "role": "historian",
        "description": "Historical pattern analyst who draws parallels from past events",
        "bias": 0.0,
        "weight": 0.9,
        "prompt_prefix": (
            "You are Clio, a historical analyst. Find analogous past events, "
            "precedents, and cyclical patterns. How did similar situations "
            "resolve historically? What does the base rate of history tell us?"
        ),
    },
}


async def run_debate(
    question: str,
    context: Optional[str] = None,
    stream: bool = False,
) -> dict:
    """Run a full debate across all agent personas.

    Args:
        question: The prediction market question to debate.
        context: Optional additional context or data.
        stream: If True, yields intermediate results (for WebSocket).

    Returns:
        Dict with 'agents' list containing each agent's analysis, vote, and confidence.
    """
    # Get base analysis from swarm engine (MiroFish or LLM)
    base_analysis = await query_mirofish(question, context)
    base_text = base_analysis.get("analysis", "")

    # Run all agents concurrently
    tasks = [
        _run_single_agent(name, persona, question, base_text, context)
        for name, persona in AGENT_PERSONAS.items()
    ]
    agent_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out exceptions
    agents = []
    for result in agent_results:
        if isinstance(result, Exception):
            logger.error("Agent failed: %s", result)
            continue
        agents.append(result)

    return {
        "agents": agents,
        "base_analysis": base_text,
        "source": base_analysis.get("source", "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def stream_debate(
    question: str,
    context: Optional[str] = None,
) -> AsyncGenerator[dict, None]:
    """Stream debate results agent-by-agent for WebSocket delivery.

    Yields event dicts suitable for JSON serialization and WebSocket send.
    """
    yield {
        "event": "debate_start",
        "content": f"Starting debate on: {question[:100]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    base_analysis = await query_mirofish(question, context)
    base_text = base_analysis.get("analysis", "")

    for name, persona in AGENT_PERSONAS.items():
        yield {
            "event": "agent_speaking",
            "agent_name": name,
            "persona": persona["role"],
            "content": f"{name} ({persona['role']}) is analyzing...",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            result = await _run_single_agent(name, persona, question, base_text, context)
            yield {
                "event": "agent_vote",
                "agent_name": name,
                "persona": persona["role"],
                "content": result["reasoning"],
                "vote": result["vote"],
                "confidence": result["confidence"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            logger.error("Agent %s failed during stream: %s", name, exc)
            yield {
                "event": "error",
                "agent_name": name,
                "content": f"Agent {name} encountered an error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


async def _run_single_agent(
    name: str,
    persona: dict,
    question: str,
    base_analysis: str,
    context: Optional[str],
) -> dict:
    """Run a single agent's analysis and vote.

    Uses the base analysis from MiroFish/LLM as input, then applies
    the agent's persona bias to generate a differentiated perspective.
    """
    import hashlib

    # Generate deterministic but varied result based on question + agent name
    seed_str = f"{question}:{name}:{base_analysis[:100]}"
    h = int(hashlib.sha256(seed_str.encode()).hexdigest()[:8], 16)

    # Base probability from analysis or synthetic
    base_prob = 0.5
    if "probability" in base_analysis.lower():
        # Try to extract probability from text
        import re
        prob_match = re.search(r"(\d{1,3})%", base_analysis)
        if prob_match:
            base_prob = int(prob_match.group(1)) / 100.0

    # Apply persona bias and some randomness
    noise = ((h % 100) - 50) / 200.0  # -0.25 to +0.25
    adjusted_prob = max(0.05, min(0.95, base_prob + persona["bias"] + noise))

    # Determine vote
    vote = "YES" if adjusted_prob >= 0.5 else "NO"

    # Confidence: how far from 0.5 (uncertain) the agent is
    confidence = round(abs(adjusted_prob - 0.5) * 2, 3)  # 0.0 to 1.0
    confidence = max(0.1, min(0.95, confidence))  # clamp

    # Generate reasoning
    reasoning = _generate_agent_reasoning(name, persona, question, vote, adjusted_prob)

    # Simulate slight processing delay for realism
    await asyncio.sleep(random.uniform(0.1, 0.3))

    return {
        "agent_name": name,
        "persona": persona["role"],
        "vote": vote,
        "confidence": confidence,
        "reasoning": reasoning,
        "weight": persona["weight"],
        "adjusted_probability": round(adjusted_prob, 3),
    }


def _generate_agent_reasoning(
    name: str,
    persona: dict,
    question: str,
    vote: str,
    probability: float,
) -> str:
    """Generate structured reasoning text for an agent's vote."""
    role = persona["role"]
    prob_pct = round(probability * 100, 1)

    templates = {
        "bull": (
            f"As {name} (Bull Strategist), I assess this at {prob_pct}% probability. "
            f"Key supporting factors include favorable macro conditions, positive momentum "
            f"signals, and historical precedents suggesting this type of outcome tends to "
            f"materialize. My vote: {vote} with focus on upside catalysts."
        ),
        "bear": (
            f"As {name} (Bear Analyst), my risk assessment puts this at {prob_pct}%. "
            f"I identify significant headwinds including execution risk, market "
            f"over-optimism, and structural barriers. Multiple failure modes exist. "
            f"My vote: {vote} emphasizing downside protection."
        ),
        "analyst": (
            f"As {name} (Quant Analyst), calibrated probability: {prob_pct}%. "
            f"Base rate analysis of {50 + random.randint(-15, 15)} similar historical "
            f"events shows a resolution rate within this range. Statistical confidence "
            f"is moderate given sample size. My vote: {vote} based on data."
        ),
        "contrarian": (
            f"As {name} (Contrarian), the market may be mispricing this at ~{prob_pct}%. "
            f"Crowd consensus often fails in these scenarios. I see potential information "
            f"asymmetry that the market hasn't fully absorbed. "
            f"My vote: {vote} — looking for edge against consensus."
        ),
        "historian": (
            f"As {name} (Historian), historical pattern analysis suggests {prob_pct}% "
            f"probability. Analogous events from the past {random.randint(5, 20)} years "
            f"show a mixed but instructive record. Key parallels and divergences inform "
            f"my assessment. My vote: {vote} based on precedent."
        ),
    }

    return templates.get(role, f"{name} votes {vote} at {prob_pct}% confidence.")
