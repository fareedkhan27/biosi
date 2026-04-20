"""Application factory for the Biosi API."""

from __future__ import annotations

import logging
from time import perf_counter
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from app.api.v1.router import v1_router
from app.core.config import settings
from app.core.db import get_database_engine
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)

OPENAPI_TAGS = [
    {
        "name": "Observability/Health",
        "description": "Service liveness and observability endpoints.",
    },
    {"name": "Jobs", "description": "Data ingestion job endpoints."},
    {"name": "Events", "description": "Event CRUD endpoints."},
    {
        "name": "Reviews",
        "description": "Event approval/rejection and review workflow endpoints.",
    },
    {"name": "Dashboards", "description": "Dashboard summary and analytics endpoints."},
    {
        "name": "Intelligence",
        "description": "Deterministic interpretation endpoints for decision-ready event insights.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # type: ignore[type-arg]
    """Manage application lifecycle: startup → yield → shutdown."""
    configure_logging()
    logger.info(
        "Starting %s v%s [env=%s]", settings.app_name, settings.service_version, settings.app_env
    )
    app.state.db_engine = get_database_engine()
    yield
    logger.info("Shutting down %s", settings.app_name)
    await app.state.db_engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.service_version,
        description="Biosimilar Competitive Intelligence Platform API",
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.cors_allow_all else settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_log_middleware(request: Request, call_next):
        started = perf_counter()
        response = await call_next(request)
        duration_ms = round((perf_counter() - started) * 1000, 2)
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%s ip=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request.client.host if request.client else "unknown",
        )
        return response

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(v1_router)

    # ── Exception handlers ────────────────────────────────────────────────────
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.host, port=settings.port)
