"""Per-User AI Agent with Memory and Prediction Context.

Manages conversation history, enriches responses with prediction
and market data, and maintains per-user context windows.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import ChatMessage, ChatRole, Prediction, PredictionStatus

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are OMEN, an AI prediction market analyst and trading assistant.

Your capabilities:
- Analyze prediction markets on Polymarket
- Explain AI debate verdicts from the Oracle engine
- Provide market insights and whale movement analysis
- Help users understand their positions and trading history
- Discuss prediction confidence scores and methodology

Your personality:
- Professional but approachable
- Data-driven and analytical
- Honest about uncertainty
- Concise but thorough when needed

Rules:
- Never provide financial advice — only analysis and information
- Always disclose when data is estimated or synthetic
- Reference specific predictions and whale data when relevant
- Be transparent about the AI debate methodology
"""

MAX_CONTEXT_MESSAGES = 20  # Maximum messages to include in context window


async def generate_response(
    session: AsyncSession,
    user_id: uuid.UUID,
    message: str,
    context_market_id: Optional[str] = None,
) -> dict:
    """Generate an AI response for a user's chat message.

    Builds a context window from recent chat history, enriches with
    prediction data if a market context is provided, and calls the
    LLM for a response.

    Args:
        session: Database session.
        user_id: Current user's ID.
        message: User's message text.
        context_market_id: Optional market ID for context enrichment.

    Returns:
        Dict with 'content' (response text) and 'tokens_used'.
    """
    # Save user message to DB
    user_msg = ChatMessage(
        user_id=user_id,
        role=ChatRole.USER,
        content=message,
        metadata_json={"market_id": context_market_id} if context_market_id else None,
    )
    session.add(user_msg)
    await session.flush()

    # Build context window
    context_messages = await _build_context_window(session, user_id)

    # Enrich with prediction data if market context provided
    enrichment = ""
    if context_market_id:
        enrichment = await _get_market_enrichment(session, user_id, context_market_id)

    # Build LLM messages
    llm_messages = _build_llm_messages(context_messages, enrichment)

    # Call LLM
    response_text, tokens = await _call_llm(llm_messages)

    # Save assistant response to DB
    assistant_msg = ChatMessage(
        user_id=user_id,
        role=ChatRole.ASSISTANT,
        content=response_text,
        metadata_json={"tokens_used": tokens, "market_id": context_market_id},
    )
    session.add(assistant_msg)
    await session.flush()

    return {
        "content": response_text,
        "tokens_used": tokens,
        "message_id": assistant_msg.id,
    }


async def _build_context_window(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> list[dict]:
    """Load the most recent chat messages for context."""
    result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(MAX_CONTEXT_MESSAGES)
    )
    messages = list(reversed(result.scalars().all()))

    return [
        {"role": msg.role.value, "content": msg.content}
        for msg in messages
    ]


async def _get_market_enrichment(
    session: AsyncSession,
    user_id: uuid.UUID,
    market_id: str,
) -> str:
    """Fetch recent predictions for a market to enrich the context."""
    result = await session.execute(
        select(Prediction)
        .where(
            Prediction.user_id == user_id,
            Prediction.market_id == market_id,
            Prediction.status == PredictionStatus.COMPLETED,
        )
        .order_by(Prediction.created_at.desc())
        .limit(3)
    )
    predictions = result.scalars().all()

    if not predictions:
        return ""

    parts = ["\n[Context: Recent predictions for this market]"]
    for p in predictions:
        parts.append(
            f"- Prediction {p.id}: Verdict={p.verdict}, "
            f"Confidence={p.confidence:.1%}, "
            f"Whale Alignment={p.whale_alignment or 0:+.2f}, "
            f"Date={p.created_at.strftime('%Y-%m-%d %H:%M')}"
        )

    return "\n".join(parts)


def _build_llm_messages(
    context_messages: list[dict],
    enrichment: str = "",
) -> list[dict]:
    """Build the full message list for the LLM call."""
    system_content = SYSTEM_PROMPT
    if enrichment:
        system_content += f"\n\n{enrichment}"

    messages = [{"role": "system", "content": system_content}]
    messages.extend(context_messages)
    return messages


async def _call_llm(messages: list[dict]) -> tuple[str, int]:
    """Call the LLM via OpenRouter API.

    Returns (response_text, tokens_used).
    Falls back to synthetic response in dev mode.
    """
    api_key = settings.openrouter_api_key
    if not api_key or api_key == "sk-placeholder":
        return _synthetic_chat_response(messages), 0

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.llm_model,
                    "messages": messages,
                    "max_tokens": 1000,
                    "temperature": 0.7,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return content, tokens
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        return _synthetic_chat_response(messages), 0


def _synthetic_chat_response(messages: list[dict]) -> str:
    """Generate a synthetic response for dev/demo mode."""
    last_user_msg = ""
    for msg in reversed(messages):
        if msg["role"] == "user":
            last_user_msg = msg["content"]
            break

    lower = last_user_msg.lower()

    if any(w in lower for w in ["predict", "oracle", "debate"]):
        return (
            "The Oracle engine uses a 5-agent debate system: Atlas (bull), "
            "Nemesis (bear), Quant (data analyst), Maverick (contrarian), "
            "and Clio (historian). Each agent analyzes the market from their "
            "unique perspective and casts a weighted vote. The final verdict "
            "is adjusted by whale position alignment for additional confidence.\n\n"
            "Would you like me to run a prediction on a specific market?"
        )
    elif any(w in lower for w in ["whale", "copy", "track"]):
        return (
            "I can help you track whale wallets and set up copy trading. "
            "The whale tracker monitors top Polymarket wallets for position "
            "changes and generates alerts for new entries, increases, and exits.\n\n"
            "Check `/whale/leaderboard` to see the top performers, or use "
            "`/trading/copy/start` to begin mirroring a whale's positions."
        )
    elif any(w in lower for w in ["credit", "balance", "purchase", "price"]):
        return (
            "OMEN uses a credit system:\n"
            "- **$5 = 50 credits** ($0.10 per credit)\n"
            "- 1 credit per prediction query\n"
            "- 1% fee on trades placed\n"
            "- 1% fee on winning profits\n\n"
            "Check your balance at `/credits/balance` or purchase more at `/credits/purchase`."
        )
    elif any(w in lower for w in ["help", "what can", "how do"]):
        return (
            "Here's what I can help with:\n\n"
            "🔮 **Predictions** — Run AI-powered market analysis with the Oracle engine\n"
            "🐋 **Whale Tracking** — Monitor top wallets and set up alerts\n"
            "📊 **Trading** — Execute trades and set up copy-trading\n"
            "💰 **Credits** — Check balance and manage purchases\n"
            "📈 **Analysis** — Discuss market trends and prediction confidence\n\n"
            "Just ask about any market or feature!"
        )
    else:
        return (
            f"Thanks for your message. I'm OMEN, your AI prediction market assistant. "
            f"I can analyze markets, track whale movements, and help you make informed "
            f"trading decisions on Polymarket.\n\n"
            f"What would you like to explore?"
        )


async def clear_history(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> int:
    """Delete all chat messages for a user. Returns count deleted."""
    from sqlalchemy import delete
    result = await session.execute(
        delete(ChatMessage).where(ChatMessage.user_id == user_id)
    )
    await session.flush()
    count = result.rowcount
    logger.info("Cleared %d chat messages for user %s", count, user_id)
    return count
