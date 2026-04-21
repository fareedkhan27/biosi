"""Schemas for ingestion and webhook endpoints."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClinicalTrialsIngestionResponse(BaseModel):
    status: Literal["ok"]
    created: int
    updated: int
    skipped: int


class N8NWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    competitor_name: str
    drug_name: str
    country: str | None = None
    event_date: date | None = None
    raw_text: str | None = None


class N8NWebhookIngestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["n8n"]
    workflow_id: str
    event_type: Literal["press_release", "clinical_trial", "manual"]
    payload: N8NWebhookPayload


class N8NWebhookIngestionResponse(BaseModel):
    received: Literal[True]
    event_id: str
    threat_score: int
    traffic_light: Literal["Red", "Amber", "Green"]
    message: str


class ExtractedEventPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    competitor_name: str | None = None
    asset_code: str | None = None
    molecule_name: str | None = None
    reference_brand: str | None = None
    event_type: str | None = None
    event_subtype: str | None = None
    development_stage: str | None = None
    indication: str | None = None
    region: str | None = None
    country: str | None = None
    event_date: str | None = None
    summary: str | None = None
    evidence_excerpt: str | None = None
    confidence_score: int | None = None


class PressReleaseIngestionRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "text": "Henlius announced FDA IND clearance for HLX18 and initiation of a Phase 3 NSCLC study.",
                "source_url": "https://example.com/press-release/hlx18-phase3",
            }
        },
    )

    text: str = Field(
        ...,
        min_length=1,
        description="Raw press-release text to extract one biosimilar CI event from.",
        examples=["Company announced initiation of a Phase 3 trial for ABP 206 in NSCLC."],
    )
    source_url: str | None = Field(
        default=None,
        max_length=2048,
        description="Optional canonical URL for deduplication and traceability.",
        examples=["https://example.com/press-release/hlx18-phase3"],
    )

    @field_validator("text")
    @classmethod
    def _validate_text_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field 'text' is required and cannot be blank.")
        return cleaned

    @field_validator("source_url")
    @classmethod
    def _normalize_source_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class PressReleaseIngestionResponse(BaseModel):
    source: Literal["press_release"]
    source_document_created: bool
    source_document_updated: bool
    event_created: bool
    event_updated: bool
    extracted_event: ExtractedEventPayload


class RecomputeScoresResponse(BaseModel):
    status: Literal["ok"]
    events_processed: int
    events_updated: int
    events_skipped: int
    avg_threat_score_before: float | None = None
    avg_threat_score_after: float | None = None
