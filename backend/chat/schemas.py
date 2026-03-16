"""Pydantic v2 schemas for chat endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """User message to the AI chat assistant."""
    message: str = Field(min_length=1, max_length=5000)
    context_market_id: Optional[str] = Field(
        default=None, description="Optional market ID for context-aware responses",
    )


class ChatMessageSchema(BaseModel):
    """Single chat message record."""
    id: uuid.UUID
    role: str
    content: str
    metadata_json: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatHistory(BaseModel):
    """Paginated chat history."""
    messages: list[ChatMessageSchema]
    total: int
    page: int
    page_size: int


class ChatResponse(BaseModel):
    """AI assistant response."""
    message: ChatMessageSchema
    tokens_used: int = 0
