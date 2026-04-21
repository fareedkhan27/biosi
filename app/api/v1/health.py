from fastapi import APIRouter
from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.schemas.health import HealthResponse, N8NHealthResponse

router = APIRouter(tags=["Observability/Health"])


@router.get(
    "/health",
    summary="Health check",
    response_model=HealthResponse,
    responses={
        200: {"description": "Service and DB are healthy"},
        503: {"description": "Database connectivity check failed"},
    },
)
async def health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Returns liveness payload; verifies database connectivity."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        raise HTTPException(status_code=503, detail="Database connectivity check failed") from exc
    return HealthResponse(status="ok")


@router.get(
    "/health/n8n",
    summary="n8n orchestration health check",
    response_model=N8NHealthResponse,
    responses={200: {"description": "Service, DB, and config checks passed"}},
)
async def health_n8n(db: AsyncSession = Depends(get_db)) -> N8NHealthResponse:
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        raise HTTPException(status_code=503, detail="Database connectivity check failed") from exc

    return N8NHealthResponse(
        status="ok",
        db="connected",
        openrouter="configured" if settings.openrouter_api_key else "not_configured",
        version=settings.service_version,
        timestamp=datetime.now(timezone.utc),
    )
