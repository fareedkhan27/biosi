"""Pydantic schemas for Event endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    competitor_id: uuid.UUID
    event_type: str
    title: str
    description: str | None = None
    event_date: date | None = None
    # Optional enrichment fields
    region: str | None = None
    country: str | None = None
    traffic_light: str | None = None
    threat_score: float | None = None
    development_stage: str | None = None
    indication: str | None = None
    metadata_json: dict[str, Any] | None = None


class EventUpdate(BaseModel):
    event_type: str | None = None
    title: str | None = None
    description: str | None = None
    event_date: date | None = None
    region: str | None = None
    country: str | None = None
    traffic_light: str | None = None
    threat_score: float | None = None
    development_stage: str | None = None
    indication: str | None = None
    metadata_json: dict[str, Any] | None = None


class EventRead(BaseModel):
    id: uuid.UUID
    competitor_id: uuid.UUID
    event_type: str
    title: str
    description: str | None = None
    event_date: date | None = None
    region: str | None = None
    country: str | None = None
    traffic_light: str | None = None
    threat_score: float | None = None
    development_stage: str | None = None
    indication: str | None = None
    metadata_json: dict[str, Any] | None = None
    review_status: str = "pending"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
