import hashlib
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.models.competitor import Competitor
from app.models.event import Event
from app.models.source import Source
from app.models.source_document import SourceDocument
from app.schemas.event import EventCreate, EventUpdate
from app.schemas.ingestion import (
    ClinicalTrialsIngestionResponse,
    ExtractedEventPayload,
    N8NWebhookIngestionRequest,
    N8NWebhookIngestionResponse,
    PressReleaseIngestionRequest,
    PressReleaseIngestionResponse,
)
from app.services.clinicaltrials_service import ClinicalTrialsIngestionService
from app.services.event_service import create_event, update_event
from app.services.press_release_service import PressReleaseIngestionService
from app.services.scoring_service import assign_traffic_light, calculate_threat_score

router = APIRouter(tags=["Jobs"])


@router.post(
    "/jobs/ingest/clinicaltrials",
    summary="Run ClinicalTrials.gov ingestion job",
    response_model=ClinicalTrialsIngestionResponse,
)
async def ingest_clinicaltrials_job(
    db: AsyncSession = Depends(get_db),
) -> ClinicalTrialsIngestionResponse:
    try:
        service = ClinicalTrialsIngestionService(
            session=db,
            base_url=settings.clinicaltrials_base_url,
            search_terms=settings.clinicaltrials_search_terms,
        )
        result = await service.ingest_default_terms()
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {"type": "validation_error", "message": str(exc)}},
        ) from exc
    except ExternalServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error": {
                    "type": "external_service_error",
                    "service": exc.service,
                    "message": str(exc),
                }
            },
        ) from exc

    created = int(result.events_created)
    updated = int(result.events_updated)
    skipped = max(0, int(result.studies_seen) - created - updated)

    return ClinicalTrialsIngestionResponse(
        status="ok",
        created=created,
        updated=updated,
        skipped=skipped,
    )


def _map_webhook_event_type(value: str) -> str:
    mapping = {
        "press_release": "press_release_update",
        "clinical_trial": "clinical_trial_update",
        "manual": "manual",
    }
    return mapping.get(value, "manual")


async def _get_or_create_competitor(db: AsyncSession, competitor_name: str) -> Competitor:
    result = await db.execute(select(Competitor).where(Competitor.name == competitor_name))
    competitor = result.scalar_one_or_none()
    if competitor is not None:
        return competitor

    competitor = Competitor(name=competitor_name, company_type="biosimilar_developer", is_active=True)
    db.add(competitor)
    await db.flush()
    return competitor


async def _get_or_create_n8n_source(db: AsyncSession) -> Source:
    result = await db.execute(select(Source).where(Source.key == "n8n_webhook"))
    source = result.scalar_one_or_none()
    if source is not None:
        return source

    source = Source(
        key="n8n_webhook",
        name="n8n Webhook",
        source_type="webhook",
        base_url=settings.n8n_webhook_base_url,
        is_active=True,
    )
    db.add(source)
    await db.flush()
    return source


def _webhook_external_id(payload: N8NWebhookIngestionRequest) -> str:
    raw = (
        f"{payload.workflow_id}|{payload.event_type}|{payload.payload.title}|"
        f"{payload.payload.competitor_name}|{payload.payload.drug_name}|"
        f"{payload.payload.event_date}|{payload.payload.raw_text or ''}"
    )
    digest = hashlib.sha256(raw.lower().strip().encode("utf-8")).hexdigest()[:24]
    return f"n8n-{digest}"


@router.post(
    "/webhooks/n8n/event",
    summary="Ingest n8n webhook event payload",
    response_model=N8NWebhookIngestionResponse,
    status_code=201,
)
async def ingest_n8n_webhook_event(
    payload: N8NWebhookIngestionRequest,
    db: AsyncSession = Depends(get_db),
) -> N8NWebhookIngestionResponse:
    competitor = await _get_or_create_competitor(db, payload.payload.competitor_name.strip())
    source = await _get_or_create_n8n_source(db)
    external_id = _webhook_external_id(payload)

    doc_result = await db.execute(
        select(SourceDocument).where(
            SourceDocument.source_id == source.id,
            SourceDocument.external_id == external_id,
        )
    )
    source_document = doc_result.scalar_one_or_none()
    if source_document is None:
        source_document = SourceDocument(
            source_id=source.id,
            external_id=external_id,
            title=payload.payload.title,
            url=f"urn:n8n:{payload.workflow_id}:{external_id}",
            raw_payload=payload.model_dump(mode="json"),
        )
        db.add(source_document)
        await db.flush()

    event_type = _map_webhook_event_type(payload.event_type)
    score = calculate_threat_score(
        event_type=event_type,
        country=payload.payload.country,
    )
    traffic_light = assign_traffic_light(score)

    event_result = await db.execute(
        select(Event).where(
            Event.competitor_id == competitor.id,
            Event.event_type == event_type,
            Event.title == payload.payload.title,
        ).order_by(desc(Event.created_at))
    )
    existing = event_result.scalars().first()

    metadata = {
        "source": "n8n",
        "workflow_id": payload.workflow_id,
        "drug_name": payload.payload.drug_name,
        "reference_drug_name": payload.payload.drug_name,
        "country": payload.payload.country,
    }

    if existing is None:
        created = await create_event(
            db,
            EventCreate(
                competitor_id=competitor.id,
                event_type=event_type,
                title=payload.payload.title,
                description=payload.payload.raw_text,
                event_date=payload.payload.event_date,
                country=payload.payload.country,
                metadata_json=metadata,
            ),
        )
        event_id = str(created.id)
        threat_score = int(created.threat_score or score)
        traffic = created.traffic_light or traffic_light
    else:
        updated = await update_event(
            db,
            str(existing.id),
            EventUpdate(
                title=payload.payload.title,
                description=payload.payload.raw_text,
                event_date=payload.payload.event_date,
                country=payload.payload.country,
                metadata_json=metadata,
            ),
        )
        event_id = str(updated.id if updated else existing.id)
        threat_score = int((updated.threat_score if updated else existing.threat_score) or score)
        traffic = (updated.traffic_light if updated else existing.traffic_light) or traffic_light

    return N8NWebhookIngestionResponse(
        received=True,
        event_id=event_id,
        threat_score=threat_score,
        traffic_light=traffic,
        message="Event ingested and scored successfully",
    )


@router.post(
    "/jobs/ingest/press-release",
    summary="Run press-release extraction and ingestion job",
    response_model=PressReleaseIngestionResponse,
)
async def ingest_press_release_job(
    payload: PressReleaseIngestionRequest = Body(
        ...,
        description="Press-release free-text payload for extraction and ingestion.",
    ),
    db: AsyncSession = Depends(get_db),
) -> PressReleaseIngestionResponse:
    try:
        service = PressReleaseIngestionService(session=db)
        result = await service.ingest_press_release(text=payload.text, source_url=payload.source_url)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {"type": "validation_error", "message": str(exc)}},
        ) from exc
    except ExternalServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error": {
                    "type": "external_service_error",
                    "service": exc.service,
                    "message": str(exc),
                }
            },
        ) from exc

    return PressReleaseIngestionResponse(
        source="press_release",
        source_document_created=result.source_document_created,
        source_document_updated=result.source_document_updated,
        event_created=result.event_created,
        event_updated=result.event_updated,
        extracted_event=ExtractedEventPayload.model_validate(
            result.extracted_event.model_dump(mode="json")
        ),
    )
