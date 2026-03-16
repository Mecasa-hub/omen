"""Oracle API endpoints: predictions and live debate WebSocket."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.utils import get_current_user
from credits.service import deduct_credits
from database import get_session
from models import Prediction, PredictionStatus, TransactionType, User

from .debate_simulator import run_debate, stream_debate
from .schemas import PredictionListResponse, PredictionRequest, PredictionResponse, Verdict
from .verdict import build_full_verdict

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/oracle", tags=["oracle"])


@router.post("/predict", response_model=PredictionResponse, status_code=status.HTTP_201_CREATED)
async def create_prediction(
    body: PredictionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Create a new AI prediction by running the swarm debate engine.

    Costs 1 credit per prediction. The debate runs synchronously and returns
    the full verdict including agent votes and whale alignment score.
    """
    # Deduct 1 credit for the prediction
    await deduct_credits(
        session=session,
        user_id=current_user.id,
        amount=1,
        tx_type=TransactionType.PREDICTION,
        description=f"Prediction: {body.question[:80]}",
        metadata_json={"market_id": body.market_id},
    )

    # Create prediction record in PENDING state
    prediction = Prediction(
        user_id=current_user.id,
        market_id=body.market_id,
        question=body.question,
        status=PredictionStatus.DEBATING,
    )
    session.add(prediction)
    await session.flush()

    try:
        # Run the AI debate
        debate_result = await run_debate(
            question=body.question,
            context=body.context,
        )

        # Build full verdict with whale alignment
        verdict = await build_full_verdict(
            agent_results=debate_result["agents"],
            session=session,
            market_id=body.market_id,
        )

        # Update prediction record
        prediction.status = PredictionStatus.COMPLETED
        prediction.verdict = verdict["direction"]
        prediction.confidence = verdict["final_confidence"]
        prediction.debate_log = debate_result
        prediction.agent_votes = {"votes": verdict["agent_votes"]}
        prediction.whale_alignment = verdict["whale_alignment"]
        prediction.completed_at = datetime.now(timezone.utc)

        await session.commit()
        await session.refresh(prediction)

        logger.info(
            "Prediction completed: id=%s market=%s verdict=%s confidence=%.1f%%",
            prediction.id, body.market_id, verdict["direction"],
            verdict["final_confidence"] * 100,
        )

        return {
            "id": prediction.id,
            "market_id": prediction.market_id,
            "question": prediction.question,
            "status": prediction.status.value,
            "verdict": verdict,
            "created_at": prediction.created_at,
            "completed_at": prediction.completed_at,
            "credits_used": 1,
        }

    except Exception as exc:
        # Mark prediction as failed
        prediction.status = PredictionStatus.FAILED
        await session.commit()
        logger.error("Prediction failed for market %s: %s", body.market_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction engine error: {str(exc)}",
        ) from exc


@router.get("/predictions", response_model=PredictionListResponse)
async def list_predictions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    market_id: str | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """List the current user's predictions with optional market filter."""
    base_query = select(Prediction).where(Prediction.user_id == current_user.id)
    count_query = select(func.count()).select_from(Prediction).where(
        Prediction.user_id == current_user.id
    )

    if market_id:
        base_query = base_query.where(Prediction.market_id == market_id)
        count_query = count_query.where(Prediction.market_id == market_id)

    # Get total count
    total = (await session.execute(count_query)).scalar_one()

    # Fetch page
    offset = (page - 1) * page_size
    result = await session.execute(
        base_query.order_by(Prediction.created_at.desc()).offset(offset).limit(page_size)
    )
    predictions = result.scalars().all()

    return {
        "predictions": [
            {
                "id": p.id,
                "market_id": p.market_id,
                "question": p.question,
                "status": p.status.value,
                "verdict": _build_verdict_response(p) if p.status == PredictionStatus.COMPLETED else None,
                "created_at": p.created_at,
                "completed_at": p.completed_at,
                "credits_used": 1,
            }
            for p in predictions
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/prediction/{prediction_id}", response_model=PredictionResponse)
async def get_prediction(
    prediction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get a specific prediction by ID."""
    result = await session.execute(
        select(Prediction).where(
            Prediction.id == prediction_id,
            Prediction.user_id == current_user.id,
        )
    )
    prediction = result.scalar_one_or_none()

    if prediction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found",
        )

    return {
        "id": prediction.id,
        "market_id": prediction.market_id,
        "question": prediction.question,
        "status": prediction.status.value,
        "verdict": _build_verdict_response(prediction) if prediction.status == PredictionStatus.COMPLETED else None,
        "created_at": prediction.created_at,
        "completed_at": prediction.completed_at,
        "credits_used": 1,
    }


@router.websocket("/ws/debate")
async def debate_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming live debate results.

    Client sends: {"market_id": "...", "question": "...", "token": "..."}
    Server streams: debate events as JSON messages.
    """
    await websocket.accept()
    logger.info("Debate WebSocket connected: %s", websocket.client)

    try:
        # Wait for initial request
        raw = await websocket.receive_text()
        try:
            request = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.send_json({"event": "error", "content": "Invalid JSON"})
            await websocket.close(code=1003)
            return

        question = request.get("question", "")
        context = request.get("context")
        token = request.get("token")

        if not question:
            await websocket.send_json({"event": "error", "content": "Missing question"})
            await websocket.close(code=1003)
            return

        # Validate token if provided (optional for WebSocket — auth can be relaxed)
        if token:
            try:
                from auth.utils import decode_token
                payload = decode_token(token)
                user_id = payload.get("sub", "anonymous")
            except Exception:
                user_id = "anonymous"
        else:
            user_id = "anonymous"

        logger.info("Debate stream starting for user=%s question=%s", user_id, question[:60])

        # Stream debate events
        async for event in stream_debate(question=question, context=context):
            await websocket.send_json(event)

        # Send completion event
        await websocket.send_json({
            "event": "debate_complete",
            "content": "All agents have voted. Debate complete.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    except WebSocketDisconnect:
        logger.info("Debate WebSocket disconnected: %s", websocket.client)
    except Exception as exc:
        logger.error("Debate WebSocket error: %s", exc, exc_info=True)
        try:
            await websocket.send_json({"event": "error", "content": str(exc)})
        except Exception:
            pass
        await websocket.close(code=1011)


def _build_verdict_response(prediction: Prediction) -> dict | None:
    """Build a Verdict response dict from a completed Prediction model."""
    if prediction.status != PredictionStatus.COMPLETED:
        return None

    votes = []
    if prediction.agent_votes and "votes" in prediction.agent_votes:
        for v in prediction.agent_votes["votes"]:
            votes.append({
                "agent_name": v.get("agent_name", ""),
                "persona": v.get("persona", ""),
                "vote": v.get("vote", ""),
                "confidence": v.get("confidence", 0.5),
                "reasoning": v.get("reasoning", ""),
                "weight": v.get("weight", 1.0),
            })

    whale_alignment = prediction.whale_alignment or 0.0
    base_confidence = prediction.confidence or 0.5

    return {
        "direction": prediction.verdict or "YES",
        "confidence": base_confidence,
        "agent_votes": votes,
        "whale_alignment": whale_alignment,
        "final_confidence": base_confidence,
        "reasoning_summary": f"Verdict: {prediction.verdict} at {base_confidence:.1%} confidence (whale alignment: {whale_alignment:+.2f})",
    }
