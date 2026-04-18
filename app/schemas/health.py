"""Pydantic schemas for the health-check endpoint."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
