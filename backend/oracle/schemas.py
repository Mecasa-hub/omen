"""Pydantic v2 schemas for the Oracle prediction engine."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    """Request to generate a new AI prediction."""
    market_id: str = Field(description="Polymarket market/condition ID")
    question: str = Field(min_length=5, max_length=1000, description="Market question text")
    context: Optional[str] = Field(
        default=None, max_length=5000,
        description="Additional context: news, data, user notes",
    )


class AgentVote(BaseModel):
    """A single AI agent's vote in the debate."""
    agent_name: str
    persona: str
    vote: str = Field(description="YES or NO")
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    weight: float = Field(description="Agent weight in consensus")


class Verdict(BaseModel):
    """Final consensus verdict from the AI debate."""
    direction: str = Field(description="YES or NO")
    confidence: float = Field(ge=0.0, le=1.0)
    agent_votes: list[AgentVote]
    whale_alignment: float = Field(
        ge=-1.0, le=1.0,
        description="-1 = whales disagree, 0 = neutral, 1 = whales agree",
    )
    final_confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence after whale alignment adjustment",
    )
    reasoning_summary: str


class PredictionResponse(BaseModel):
    """Full prediction result returned to the user."""
    id: uuid.UUID
    market_id: str
    question: str
    status: str
    verdict: Optional[Verdict] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    credits_used: int = 1

    model_config = {"from_attributes": True}


class DebateMessage(BaseModel):
    """WebSocket message during live debate streaming."""
    event: str = Field(description="debate_start, agent_speaking, agent_vote, verdict, error")
    agent_name: Optional[str] = None
    persona: Optional[str] = None
    content: str
    timestamp: datetime


class PredictionListResponse(BaseModel):
    """Paginated list of user predictions."""
    predictions: list[PredictionResponse]
    total: int
    page: int
    page_size: int
