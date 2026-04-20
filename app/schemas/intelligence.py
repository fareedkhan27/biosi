"""Pydantic response models for additive intelligence endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class IntelligenceInsightItem(BaseModel):
    id: str
    competitor_id: str
    competitor_name: str
    event_type: str
    title: str
    event_date: str | None
    created_at: str | None
    review_status: str
    threat_score: int
    traffic_light: str | None
    development_stage: str | None
    indication: str | None
    country: str | None
    region: str | None
    competitor_tier: int | None
    estimated_launch_year: int | str | None
    score_breakdown: dict[str, Any] | None
    summary: str
    risk_reason: str
    recommended_action: str | None
    confidence_note: str | None


class CompetitorSummaryItem(BaseModel):
    competitor_name: str
    event_count: int
    max_score: int
    top_indication: str
    summary: str


class WeeklyDigestCounts(BaseModel):
    red: int
    amber: int
    green: int


class WeeklyDigestResponse(BaseModel):
    generated_at: str
    top_insights: list[IntelligenceInsightItem]
    competitor_summary: list[CompetitorSummaryItem]
    counts: WeeklyDigestCounts
