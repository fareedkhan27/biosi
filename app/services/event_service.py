"""Event CRUD service backed by SQLAlchemy ORM persistence."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.schemas.event import EventCreate, EventRead, EventUpdate
from app.services.scoring_service import calculate_threat_assessment

# Compatibility shim for modules not yet migrated in later phases.
# Phase B does not use this in-memory store for event persistence.
_SESSION_STORES: dict[int, dict[str, Any]] = {}

def _build_metadata(
    payload: EventCreate | EventUpdate,
    existing_metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build metadata JSON by merging existing metadata with top-level optional fields."""
    metadata: dict[str, Any] = dict(existing_metadata or {})

    if payload.metadata_json:
        metadata.update(payload.metadata_json)

    for key in ("region", "country", "development_stage", "indication"):
        value = getattr(payload, key, None)
        if value is not None:
            metadata[key] = value

    return metadata or None


def _extract_scoring_inputs(
    *,
    event_type: str,
    metadata_json: dict[str, Any] | None,
) -> tuple[str, str | None, int | None, str | None, str | None, str | None, int | None, str | None]:
    """Extract scoring inputs from explicit fields and metadata JSON."""
    metadata = metadata_json or {}

    development_stage = metadata.get("development_stage")
    region = metadata.get("region")
    country = metadata.get("country")
    indication = metadata.get("indication")
    competitor_tier = metadata.get("competitor_tier")
    competitor_geography = metadata.get("competitor_geography")

    confidence_score_raw = metadata.get("confidence_score")
    confidence_score: int | None = None
    if isinstance(confidence_score_raw, int):
        confidence_score = confidence_score_raw
    elif isinstance(confidence_score_raw, str) and confidence_score_raw.isdigit():
        confidence_score = int(confidence_score_raw)

    return (
        event_type,
        development_stage,
        confidence_score,
        region,
        country,
        indication,
        competitor_tier,
        competitor_geography,
    )


def _to_event_read(event: Event) -> EventRead:
    """Map ORM Event row to API schema, including metadata-derived convenience fields."""
    metadata = event.metadata_json or {}
    return EventRead(
        id=event.id,
        competitor_id=event.competitor_id,
        event_type=event.event_type,
        title=event.title,
        description=event.description,
        event_date=event.event_date,
        region=metadata.get("region"),
        country=metadata.get("country"),
        traffic_light=event.traffic_light,
        threat_score=float(event.threat_score) if event.threat_score is not None else None,
        development_stage=metadata.get("development_stage"),
        indication=metadata.get("indication"),
        metadata_json=event.metadata_json,
        review_status=event.review_status,
        created_at=event.created_at,
    )


def _scoring_inputs_changed(updates: dict[str, Any]) -> bool:
    """Return True if update payload touches fields that should trigger score recompute."""
    scoring_keys = {"event_type", "region", "country", "development_stage", "indication", "metadata_json"}
    return any(key in updates for key in scoring_keys)


def _safe_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None


async def create_event(session: AsyncSession, data: EventCreate) -> EventRead:
    metadata_json = _build_metadata(data)

    (
        event_type,
        development_stage,
        confidence_score,
        region,
        country,
        indication,
        competitor_tier,
        competitor_geography,
    ) = _extract_scoring_inputs(
        event_type=data.event_type,
        metadata_json=metadata_json,
    )
    assessment = calculate_threat_assessment(
        event_type=event_type,
        development_stage=development_stage,
        competitor_tier=competitor_tier,
        confidence_score=confidence_score,
        region=region,
        country=country,
        indication=indication,
        competitor_geography=competitor_geography,
    )
    if metadata_json is None:
        metadata_json = {}
    metadata_json["score_breakdown"] = assessment["score_breakdown"]
    threat_score = assessment["threat_score"]
    traffic_light = assessment["traffic_light"]

    event = Event(
        id=uuid.uuid4(),
        competitor_id=data.competitor_id,
        event_type=data.event_type,
        title=data.title,
        description=data.description,
        event_date=data.event_date,
        indication=data.indication,
        metadata_json=metadata_json,
        threat_score=threat_score,
        traffic_light=traffic_light,
        review_status="pending",
    )

    session.add(event)
    await session.commit()
    await session.refresh(event)
    return _to_event_read(event)


async def get_event(session: AsyncSession, event_id: str) -> EventRead | None:
    parsed_id = _safe_uuid(event_id)
    if parsed_id is None:
        return None

    result = await session.execute(select(Event).where(Event.id == parsed_id))
    event = result.scalar_one_or_none()
    if event is None:
        return None
    return _to_event_read(event)


async def list_events(
    session: AsyncSession,
    traffic_light: str | None = None,
    event_type: str | None = None,
    region: str | None = None,
    country: str | None = None,
) -> list[EventRead]:
    stmt = select(Event)
    if traffic_light is not None:
        stmt = stmt.where(Event.traffic_light == traffic_light)
    if event_type is not None:
        stmt = stmt.where(Event.event_type == event_type)

    result = await session.execute(stmt)
    events = list(result.scalars().all())

    # Region/country currently live in metadata_json. Filter in Python for readability.
    if region is not None:
        events = [e for e in events if (e.metadata_json or {}).get("region") == region]
    if country is not None:
        events = [e for e in events if (e.metadata_json or {}).get("country") == country]

    return [_to_event_read(event) for event in events]


async def update_event(session: AsyncSession, event_id: str, data: EventUpdate) -> EventRead | None:
    parsed_id = _safe_uuid(event_id)
    if parsed_id is None:
        return None

    result = await session.execute(select(Event).where(Event.id == parsed_id))
    event = result.scalar_one_or_none()
    if event is None:
        return None

    updates = data.model_dump(exclude_unset=True)

    if "event_type" in updates:
        event.event_type = updates["event_type"]
    if "title" in updates:
        event.title = updates["title"]
    if "description" in updates:
        event.description = updates["description"]
    if "event_date" in updates:
        event.event_date = updates["event_date"]

    if any(key in updates for key in ("metadata_json", "region", "country", "development_stage", "indication")):
        event.metadata_json = _build_metadata(data, existing_metadata=event.metadata_json)
    if "indication" in updates:
        event.indication = updates["indication"]

    if _scoring_inputs_changed(updates):
        (
            event_type,
            development_stage,
            confidence_score,
            region_value,
            country_value,
            indication_value,
            competitor_tier,
            competitor_geography,
        ) = _extract_scoring_inputs(
            event_type=event.event_type,
            metadata_json=event.metadata_json,
        )
        assessment = calculate_threat_assessment(
            event_type=event_type,
            development_stage=development_stage,
            competitor_tier=competitor_tier,
            confidence_score=confidence_score,
            region=region_value,
            country=country_value,
            indication=indication_value,
            competitor_geography=competitor_geography,
        )
        if event.metadata_json is None:
            event.metadata_json = {}
        event.metadata_json["score_breakdown"] = assessment["score_breakdown"]
        event.threat_score = assessment["threat_score"]
        event.traffic_light = assessment["traffic_light"]
    else:
        # Preserve compatibility for explicit direct updates if provided.
        if "threat_score" in updates and updates["threat_score"] is not None:
            event.threat_score = int(updates["threat_score"])
        if "traffic_light" in updates:
            event.traffic_light = updates["traffic_light"]

    await session.commit()
    await session.refresh(event)
    return _to_event_read(event)
