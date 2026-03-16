"""MiroFish API wrapper and swarm orchestration.

Connects to a local MiroFish instance (or falls back to OpenRouter LLM)
to power the AI agent debate system.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

_http_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    """Lazy-initialize a shared async HTTP client."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=60.0)
    return _http_client


async def close_client() -> None:
    """Close the shared HTTP client on shutdown."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


async def check_mirofish_health() -> bool:
    """Check whether the MiroFish backend is reachable."""
    try:
        client = _get_client()
        resp = await client.get(f"{settings.mirofish_url}/health", timeout=5.0)
        return resp.status_code == 200
    except Exception as exc:
        logger.debug("MiroFish health check failed: %s", exc)
        return False


async def query_mirofish(
    question: str,
    context: Optional[str] = None,
) -> dict:
    """Query MiroFish for a prediction analysis.

    Attempts MiroFish first; falls back to direct OpenRouter LLM call.
    Returns a dict with 'analysis' text and 'source' indicator.
    """
    # Try MiroFish first
    if await check_mirofish_health():
        try:
            client = _get_client()
            payload = {
                "question": question,
                "context": context or "",
                "mode": "quick",
            }
            resp = await client.post(
                f"{settings.mirofish_url}/api/report/generate",
                json=payload,
                timeout=45.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                logger.info("MiroFish prediction received for: %s", question[:60])
                return {
                    "analysis": data.get("report", data.get("result", str(data))),
                    "source": "mirofish",
                    "raw": data,
                }
        except Exception as exc:
            logger.warning("MiroFish query failed, falling back to LLM: %s", exc)

    # Fallback: direct LLM call via OpenRouter
    return await _query_openrouter(question, context)


async def _query_openrouter(
    question: str,
    context: Optional[str] = None,
) -> dict:
    """Direct LLM query via OpenRouter as fallback."""
    api_key = settings.openrouter_api_key
    if not api_key or api_key == "sk-placeholder":
        # Dev mode: return synthetic analysis
        logger.info("Dev mode: generating synthetic analysis for: %s", question[:60])
        return _synthetic_analysis(question)

    prompt = _build_analysis_prompt(question, context)

    try:
        client = _get_client()
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1500,
                "temperature": 0.7,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        logger.info("OpenRouter analysis received for: %s", question[:60])
        return {"analysis": content, "source": "openrouter", "raw": data}
    except Exception as exc:
        logger.error("OpenRouter query failed: %s", exc)
        return _synthetic_analysis(question)


def _build_analysis_prompt(question: str, context: Optional[str] = None) -> str:
    """Build the analysis prompt for the LLM."""
    parts = [
        "You are a prediction market analyst. Analyze this market question "
        "and provide a detailed assessment including probability estimate, "
        "key factors, risks, and your reasoning.",
        f"\nQuestion: {question}",
    ]
    if context:
        parts.append(f"\nAdditional context: {context}")
    parts.append(
        "\nProvide your analysis in a structured format with:\n"
        "1. Summary assessment\n"
        "2. Key supporting factors\n"
        "3. Key risk factors\n"
        "4. Probability estimate (0-100%)\n"
        "5. Confidence level (low/medium/high)"
    )
    return "\n".join(parts)


def _synthetic_analysis(question: str) -> dict:
    """Generate synthetic analysis for dev/demo mode."""
    import hashlib

    # Deterministic but varied synthetic responses based on question hash
    h = int(hashlib.md5(question.encode()).hexdigest()[:8], 16)
    prob = 30 + (h % 41)  # 30-70%
    confidence = ["medium", "high", "medium-high"][h % 3]

    analysis = (
        f"## Analysis: {question[:100]}\n\n"
        f"**Probability Estimate:** {prob}%\n"
        f"**Confidence:** {confidence}\n\n"
        f"### Key Supporting Factors\n"
        f"- Historical patterns suggest moderate likelihood\n"
        f"- Market sentiment currently {'bullish' if prob > 50 else 'bearish'}\n"
        f"- Multiple data points support this assessment\n\n"
        f"### Risk Factors\n"
        f"- Uncertainty in underlying drivers\n"
        f"- Potential for unexpected catalysts\n"
        f"- Limited historical precedent for exact scenario\n\n"
        f"### Summary\n"
        f"Based on available evidence, this market has a {prob}% probability "
        f"of resolving YES. The assessment carries {confidence} confidence."
    )
    return {"analysis": analysis, "source": "synthetic", "raw": {"probability": prob}}
