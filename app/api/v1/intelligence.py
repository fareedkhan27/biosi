"""Additive intelligence endpoints for deterministic weekly digest output."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.intelligence import WeeklyDigestResponse
from app.services import dashboard_service
from app.services.intelligence_interpreter import build_weekly_digest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])


@router.get("/digest")
async def get_intelligence_digest(
    top_limit: int = Query(10, ge=1, le=50),
    recent_limit: int = Query(20, ge=1, le=100),
    since_hours: int | None = None,
    since_days: int | None = None,
    approved_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Single-call, email-ready bundle for n8n."""
    try:
        top_threats = await dashboard_service.get_top_threats(
            db, limit=top_limit, approved_only=approved_only
        )
    except Exception as exc:
        logger.error("get_top_threats failed: %s", exc)
        top_threats = []

    try:
        recent_events = await dashboard_service.get_recent_events(
            db, limit=recent_limit, since_hours=since_hours, since_days=since_days
        )
    except Exception as exc:
        logger.error("get_recent_events failed: %s", exc)
        recent_events = []

    try:
        review_queue = await dashboard_service.get_review_queue(db, limit=10)
    except Exception as exc:
        logger.error("get_review_queue failed: %s", exc)
        review_queue = []

    try:
        summary = await dashboard_service.get_summary(db)
        summary_counts = {
            "total_events": summary.total_events,
            "approved": summary.approved,
            "pending": summary.pending,
            "rejected": summary.rejected,
            "by_traffic_light": summary.by_traffic_light,
        }
    except Exception as exc:
        logger.error("get_summary failed: %s", exc)
        summary_counts = {
            "total_events": 0,
            "approved": 0,
            "pending": 0,
            "rejected": 0,
            "by_traffic_light": {},
        }

    return {
        "top_threats": top_threats,
        "recent_events": recent_events,
        "review_queue": review_queue,
        "summary_counts": summary_counts,
    }


@router.get("/weekly-digest-v2", response_model=WeeklyDigestResponse)
async def get_weekly_digest_v2(
    limit: int = Query(100, ge=1, le=100),
    approved_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> WeeklyDigestResponse:
    payload = await build_weekly_digest(db, limit=limit, approved_only=approved_only)
    return WeeklyDigestResponse.model_validate(payload)
