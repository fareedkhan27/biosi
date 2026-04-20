"""Pydantic schemas for the health-check endpoint."""

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class N8NHealthResponse(BaseModel):
    status: str
    db: str
    openrouter: str
    version: str
    timestamp: datetime
