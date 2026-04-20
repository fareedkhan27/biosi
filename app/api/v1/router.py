"""Aggregate router for API v1.

Each feature module registers its own APIRouter here, keeping
`app/main.py` free of route-level concerns.
"""

from fastapi import APIRouter

from app.api.v1.dashboards import router as dashboards_router
from app.api.v1.events import router as events_router
from app.api.v1.health import router as health_router
from app.api.v1.intelligence import router as intelligence_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.reviews import router as reviews_router

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(health_router)
v1_router.include_router(jobs_router)
v1_router.include_router(events_router)
v1_router.include_router(reviews_router)
v1_router.include_router(dashboards_router)
v1_router.include_router(intelligence_router)
