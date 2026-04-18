from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["Observability"])


@router.get(
    "/health",
    summary="Health check",
    response_model=HealthResponse,
    responses={200: {"description": "Service is healthy"}},
)
async def health() -> HealthResponse:
    """Returns service liveness status, name, and version."""
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.service_version,
    )
