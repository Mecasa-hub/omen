"""Chat API endpoints: message, history, clear, WebSocket live chat."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.utils import get_current_user
from database import get_session
from models import ChatMessage, User

from .agent import clear_history, generate_response
from .schemas import ChatHistory, ChatMessageSchema, ChatRequest, ChatResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def send_message(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Send a message to the OMEN AI assistant and get a response."""
    result = await generate_response(
        session=session,
        user_id=current_user.id,
        message=body.message,
        context_market_id=body.context_market_id,
    )

    await session.commit()

    # Fetch the saved assistant message
    msg_result = await session.execute(
        select(ChatMessage).where(ChatMessage.id == result["message_id"])
    )
    assistant_msg = msg_result.scalar_one()

    return {
        "message": assistant_msg,
        "tokens_used": result["tokens_used"],
    }


@router.get("/history", response_model=ChatHistory)
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get paginated chat history for the current user."""
    count_result = await session.execute(
        select(func.count()).select_from(ChatMessage).where(
            ChatMessage.user_id == current_user.id
        )
    )
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.asc())
        .offset(offset)
        .limit(page_size)
    )
    messages = list(result.scalars().all())

    return {
        "messages": messages,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.delete("/clear", status_code=status.HTTP_200_OK)
async def clear_chat(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Clear all chat history for the current user."""
    count = await clear_history(session, current_user.id)
    await session.commit()
    return {"message": f"Cleared {count} messages", "deleted": count}


@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time chat with the OMEN AI assistant.

    Client sends: {"message": "...", "token": "...", "context_market_id": "..."}
    Server responds: {"event": "response", "content": "...", "tokens_used": N}
    """
    await websocket.accept()
    logger.info("Chat WebSocket connected: %s", websocket.client)

    # Import here to avoid circular imports
    from auth.utils import decode_token
    from database import async_session_factory

    user_id = None

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"event": "error", "content": "Invalid JSON"})
                continue

            message = data.get("message", "").strip()
            token = data.get("token")
            context_market_id = data.get("context_market_id")

            if not message:
                await websocket.send_json({"event": "error", "content": "Empty message"})
                continue

            # Authenticate on first message or if token changes
            if token and not user_id:
                try:
                    payload = decode_token(token)
                    user_id = uuid.UUID(payload["sub"])
                except Exception:
                    await websocket.send_json({"event": "error", "content": "Invalid token"})
                    continue

            if not user_id:
                await websocket.send_json({"event": "error", "content": "Authentication required"})
                continue

            # Send typing indicator
            await websocket.send_json({
                "event": "typing",
                "content": "OMEN is thinking...",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Generate response with a fresh session
            async with async_session_factory() as db_session:
                try:
                    result = await generate_response(
                        session=db_session,
                        user_id=user_id,
                        message=message,
                        context_market_id=context_market_id,
                    )
                    await db_session.commit()

                    await websocket.send_json({
                        "event": "response",
                        "content": result["content"],
                        "tokens_used": result["tokens_used"],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception as exc:
                    logger.error("Chat response error: %s", exc, exc_info=True)
                    await websocket.send_json({
                        "event": "error",
                        "content": "Sorry, I encountered an error. Please try again.",
                    })

    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected: %s", websocket.client)
    except Exception as exc:
        logger.error("Chat WebSocket error: %s", exc, exc_info=True)
        try:
            await websocket.send_json({"event": "error", "content": str(exc)})
        except Exception:
            pass
        await websocket.close(code=1011)
