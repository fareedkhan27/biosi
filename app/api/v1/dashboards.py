"""Dashboards router – Milestone 6 summary endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.dashboard import (
    DashboardRecentEventItem,
    DashboardReviewQueueItem,
    DashboardSummaryResponse,
    DashboardTopThreatItem,
)
from app.services import dashboard_service

router = APIRouter(prefix="/dashboards", tags=["Dashboards"])


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_summary(db: AsyncSession = Depends(get_db)) -> DashboardSummaryResponse:
    return await dashboard_service.get_summary(db)


@router.get("/top-threats", response_model=list[DashboardTopThreatItem])
async def get_top_threats(
    limit: int = Query(10, ge=1, le=50),
    approved_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[DashboardTopThreatItem]:
    return await dashboard_service.get_top_threats(db, limit=limit, approved_only=approved_only)


@router.get("/recent-events", response_model=list[DashboardRecentEventItem])
async def get_recent_events(
    limit: int = Query(20, ge=1, le=100),
    since_hours: int | None = None,
    since_days: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[DashboardRecentEventItem]:
    return await dashboard_service.get_recent_events(
        db,
        limit=limit,
        since_hours=since_hours,
        since_days=since_days,
    )


@router.get("/review-queue", response_model=list[DashboardReviewQueueItem])
async def get_review_queue(
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[DashboardReviewQueueItem]:
    return await dashboard_service.get_review_queue(db, limit=limit)
