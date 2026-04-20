"""Pydantic schemas for Dashboard endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# Canonical value sets — kept here so other modules can import them.
ReviewStatus = Literal["approved", "pending", "rejected"]
TrafficLight = Literal["Green", "Amber", "Red"]


class DashboardSummaryResponse(BaseModel):
    total_events: int
    approved: int
    pending: int
    rejected: int
    by_traffic_light: dict[str, int]


class DashboardEventItem(BaseModel):
    id: str
    competitor_id: str
    competitor_name: str | None
    event_type: str
    title: str
    event_date: str | None
    created_at: str
    review_status: ReviewStatus
    threat_score: int | None
    traffic_light: TrafficLight | None


class DashboardTopThreatItem(BaseModel):
    id: str
    drug_name: str
    competitor_name: str | None
    threat_score: int
    traffic_light: TrafficLight
    event_date: str | None
    country: str | None
    indication: str | None = None
    review_status: ReviewStatus | None = None
    asset_code: str | None = None
    development_stage: str | None = None
    competitor_tier: int | None = None
    estimated_launch_year: int | str | None = None
    summary: str | None = None
    risk_reason: str | None = None
    recommended_action: str | None = None
    confidence_note: str | None = None


class DashboardRecentEventItem(DashboardEventItem):
    """Item schema for recent-event rows."""

    country: str | None = None
    indication: str | None = None
    asset_code: str | None = None
    development_stage: str | None = None
    competitor_tier: int | None = None
    estimated_launch_year: int | str | None = None
    summary: str | None = None
    risk_reason: str | None = None
    recommended_action: str | None = None
    confidence_note: str | None = None


class DashboardReviewQueueItem(DashboardEventItem):
    """Item schema for review-queue rows."""
