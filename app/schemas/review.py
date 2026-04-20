"""Pydantic schemas for Review endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ReviewStatusEnum(str, Enum):
    approved = "approved"
    pending = "pending"
    rejected = "rejected"


class ReviewCreate(BaseModel):
    event_id: uuid.UUID
    status: str = ReviewStatusEnum.pending.value  # "approved" | "rejected" | "pending"
    reviewer: str | None = None
    review_notes: str | None = None


class ApproveRejectRequest(BaseModel):
    reviewer_email: str | None = None
    comment: str | None = None


class ReviewRead(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    status: ReviewStatusEnum
    reviewer: str | None = None
    review_notes: str | None = None
    review_status: ReviewStatusEnum = ReviewStatusEnum.pending  # echoes the status for convenience
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
