"""Pydantic v2 schemas for credit system endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreditBalance(BaseModel):
    """Current user credit balance."""
    user_id: uuid.UUID
    balance: int
    usd_equivalent: float = Field(description="Balance in USD ($5 = 50 credits)")


class CreditPurchase(BaseModel):
    """Request to purchase credits."""
    amount_usd: float = Field(gt=0, le=1000, description="Amount in USD")
    payment_method_id: Optional[str] = Field(
        default=None, description="Stripe payment method ID",
    )


class CreditTransactionSchema(BaseModel):
    """Single credit transaction record."""
    id: uuid.UUID
    tx_type: str
    amount: int
    balance_after: int
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreditHistoryResponse(BaseModel):
    """Paginated list of credit transactions."""
    transactions: list[CreditTransactionSchema]
    total: int
    page: int
    page_size: int


class StripeWebhookPayload(BaseModel):
    """Stripe webhook event envelope."""
    id: str
    type: str
    data: dict
