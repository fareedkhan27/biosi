"""Dashboard aggregation service backed by SQLAlchemy database queries.

No DISTINCT ON — deduplication is handled by _dedupe_by_key after fetch.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import TypedDict

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competitor import Competitor
from app.models.event import Event

from app.schemas.dashboard import DashboardSummaryResponse

_VALID_REVIEW_STATUS = {"approved", "pending", "rejected"}
_VALID_TRAFFIC_LIGHT = {"Green", "Amber", "Red"}
_NON_COMPETITOR_NAME_TOKENS: tuple[str, ...] = (
    "university",
    "institute",
    "college",
    "hospital",
    "clinic",
    "center",
    "centre",
    "foundation",
    "oncology group",
    "nci",
    "nih",
    "swog",
    "ecog",
    "nrg",
    "gog",
    "alliance",
    "department of",
    "ministry of",
    "government",
    "federal",
)


class DashboardEventItem(TypedDict):
    id: str
    competitor_id: str
    competitor_name: str | None
    event_type: str
    title: str
    event_date: str | None
    created_at: str
    review_status: str
    threat_score: int | None
    traffic_light: str | None


class DashboardTopThreatItem(TypedDict):
    id: str
    drug_name: str
    competitor_name: str | None
    threat_score: int
    traffic_light: str
    event_date: str | None
    country: str | None
    indication: str | None
    review_status: str


class DashboardRecentEventItem(TypedDict):
    id: str
    competitor_id: str
    competitor_name: str | None
    event_type: str
    title: str
    event_date: str | None
    created_at: str
    review_status: str
    threat_score: int | None
    traffic_light: str | None
    country: str | None
    indication: str | None


def _dedupe_by_key[T](items: list[T], key_fn) -> list[T]:
    seen: set[tuple] = set()
    unique: list[T] = []
    for item in items:
        key = key_fn(item)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _as_iso_date(value: date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _as_iso_datetime(value: datetime) -> str:
    return value.isoformat()


def _normalize_review_status(value: str | None) -> str:
    raw = (value or "").strip()
    cleaned = raw.strip("\"'").strip().lower()
    if cleaned in _VALID_REVIEW_STATUS:
        return cleaned
    return "pending"


def _normalize_traffic_light(value: str | None) -> str | None:
    if value is None:
        return None

    raw = value.strip()
    cleaned = raw.strip("\"'").strip().lower()
    if not cleaned:
        return None

    canonical = cleaned.capitalize()
    if canonical in _VALID_TRAFFIC_LIGHT:
        return canonical
    return None


def _to_dashboard_event_item(event: Event, competitor_name: str | None) -> DashboardEventItem:
    return DashboardEventItem(
        id=str(event.id),
        competitor_id=str(event.competitor_id),
        competitor_name=competitor_name,
        event_type=event.event_type,
        title=event.title,
        event_date=_as_iso_date(event.event_date),
        created_at=_as_iso_datetime(event.created_at),
        review_status=_normalize_review_status(event.review_status),
        threat_score=event.threat_score,
        traffic_light=_normalize_traffic_light(event.traffic_light),
    )


def _resolve_drug_name(metadata: dict | None) -> str:
    meta = metadata or {}
    for key in ("reference_drug_name", "drug_name", "reference_brand", "molecule_name"):
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Unknown drug"


def _resolve_country(metadata: dict | None, competitor_country: str | None) -> str | None:
    meta = metadata or {}
    country = meta.get("country")
    if isinstance(country, str) and country.strip():
        return country.strip()
    return competitor_country


def _metadata_value(event: Event, key: str):
    metadata = getattr(event, "metadata_json", None) or {}
    value = metadata.get(key)
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return value


def _build_insight_fields(event: Event, competitor_name: str | None) -> dict:
    # Lazy import to avoid circular dependency (intelligence_interpreter imports from this module).
    from app.services.intelligence_interpreter import build_event_insight

    if competitor_name is not None:
        setattr(event, "_intelligence_competitor_name", competitor_name)
    try:
        insight = build_event_insight(event)
    except Exception:
        insight = {
            "summary": None,
            "risk_reason": None,
            "recommended_action": None,
            "confidence_note": None,
        }
    return {
        "asset_code": (event.metadata_json or {}).get("asset_code"),
        "development_stage": (event.metadata_json or {}).get("development_stage"),
        "competitor_tier": (event.metadata_json or {}).get("competitor_tier"),
        "estimated_launch_year": (event.metadata_json or {}).get("estimated_launch_year"),
        "summary": insight.get("summary"),
        "risk_reason": insight.get("risk_reason"),
        "recommended_action": insight.get("recommended_action"),
        "confidence_note": insight.get("confidence_note"),
    }


def _resolve_indication(event: Event) -> str | None:
    indication = getattr(event, "indication", None)
    if isinstance(indication, str) and indication.strip():
        return indication.strip()

    metadata = getattr(event, "metadata_json", None) or {}
    metadata_indication = metadata.get("indication")
    if isinstance(metadata_indication, str) and metadata_indication.strip():
        return metadata_indication.strip()
    return None


def _apply_non_competitor_name_filters(stmt):
    lowered_name = func.lower(Competitor.name)
    stmt = stmt.where(Competitor.name.is_not(None))
    for token in _NON_COMPETITOR_NAME_TOKENS:
        stmt = stmt.where(~lowered_name.contains(token))
    return stmt


async def get_summary(session: AsyncSession) -> DashboardSummaryResponse:
    total_stmt = select(func.count(Event.id))
    total_result = await session.execute(total_stmt)
    total_events = int(total_result.scalar_one() or 0)

    review_status_stmt = (
        select(Event.review_status, func.count(Event.id))
        .group_by(Event.review_status)
        .order_by(Event.review_status)
    )
    review_status_result = await session.execute(review_status_stmt)

    review_status_counts: dict[str, int] = {}
    for status, count in review_status_result.all():
        normalized = _normalize_review_status(status)
        review_status_counts[normalized] = review_status_counts.get(normalized, 0) + int(count)

    approved = review_status_counts.get("approved", 0)
    pending = review_status_counts.get("pending", 0)
    rejected = review_status_counts.get("rejected", 0)

    traffic_light_stmt = (
        select(Event.traffic_light, func.count(Event.id))
        .where(Event.traffic_light.is_not(None))
        .group_by(Event.traffic_light)
        .order_by(Event.traffic_light)
    )
    traffic_light_result = await session.execute(traffic_light_stmt)

    by_traffic_light: dict[str, int] = {}
    for traffic_light, count in traffic_light_result.all():
        if traffic_light is None:
            continue
        normalized = _normalize_traffic_light(traffic_light)
        if normalized is None:
            continue
        by_traffic_light[normalized] = by_traffic_light.get(normalized, 0) + int(count)

    return DashboardSummaryResponse(
        total_events=total_events,
        approved=approved,
        pending=pending,
        rejected=rejected,
        by_traffic_light=by_traffic_light,
    )


async def get_top_threats(
    session: AsyncSession,
    *,
    limit: int = 10,
    approved_only: bool = False,
) -> list[DashboardTopThreatItem]:
    stmt = (
        select(Event, Competitor.name, Competitor.headquarters_country)
        .join(Competitor, Event.competitor_id == Competitor.id)
        .where(Event.threat_score.is_not(None))
    )
    stmt = _apply_non_competitor_name_filters(stmt)

    if approved_only:
        stmt = stmt.where(Event.review_status == "approved")
    else:
        stmt = stmt.where(Event.review_status != "rejected")

    stmt = stmt.order_by(
        Event.threat_score.desc().nullslast(),
        Event.created_at.desc(),
        Event.event_date.desc().nullslast(),
        Event.id,
    ).limit(limit)

    result = await session.execute(stmt)
    rows = result.all()

    items: list[DashboardTopThreatItem] = []
    for row in rows:
        if len(row) == 2:
            event, competitor_name = row
            competitor_country = None
        else:
            event, competitor_name, competitor_country = row
        metadata = getattr(event, "metadata_json", None)
        items.append(
            {
                "id": str(event.id),
                "drug_name": _resolve_drug_name(metadata),
                "competitor_name": competitor_name,
                "threat_score": int(event.threat_score or 0),
                "traffic_light": _normalize_traffic_light(event.traffic_light) or "Green",
                "event_date": _as_iso_date(event.event_date),
                "country": _resolve_country(metadata, competitor_country),
                "indication": _resolve_indication(event),
                "review_status": _normalize_review_status(getattr(event, "review_status", None)),
                **_build_insight_fields(event, competitor_name),
            }
        )

    # Keep the highest-ranked event for each competitor so duplicates do not dominate.
    deduped = _dedupe_by_key(items, lambda i: (i["competitor_name"] or i["id"],))
    return deduped


async def get_recent_events(
    session: AsyncSession,
    *,
    limit: int = 10,
    include_rejected: bool = False,
    since_hours: int | None = None,
    since_days: int | None = None,
) -> list[DashboardRecentEventItem]:
    # NOTE: threat_score IS NOT NULL is intentionally absent here.
    # Recent-events must surface approved events regardless of scoring state
    # so that n8n Workflows 2 and 3 never silently miss qualifying rows.
    stmt = (
        select(Event, Competitor.name, Competitor.headquarters_country)
        .join(Competitor, Event.competitor_id == Competitor.id)
    )
    stmt = _apply_non_competitor_name_filters(stmt)

    if not include_rejected:
        stmt = stmt.where(Event.review_status != "rejected")

    # Server-side date window — enables n8n workflows to skip client-side
    # filtering and avoid the fragility of a pure limit-based approximation.
    if since_hours is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        stmt = stmt.where(Event.created_at >= cutoff)
    elif since_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        stmt = stmt.where(Event.created_at >= cutoff)

    stmt = stmt.order_by(
        Event.created_at.desc(),
        Event.threat_score.desc().nullslast(),
        Event.event_date.desc().nullslast(),
        Event.id,
    ).limit(limit)

    result = await session.execute(stmt)
    rows = result.all()

    items: list[DashboardRecentEventItem] = []
    for row in rows:
        if len(row) == 2:
            event, competitor_name = row
            competitor_country = None
        else:
            event, competitor_name, competitor_country = row
        base_item = _to_dashboard_event_item(event, competitor_name)
        items.append(
            {
                **base_item,
                "country": _resolve_country(getattr(event, "metadata_json", None), competitor_country),
                "indication": _resolve_indication(event),
                **_build_insight_fields(event, competitor_name),
            }
        )
    # Defensive dedupe in case of repeated rows from joins/data anomalies.
    return _dedupe_by_key(items, lambda i: (i["id"],))


async def get_review_queue(
    session: AsyncSession,
    *,
    limit: int = 25,
) -> list[DashboardEventItem]:
    stmt = (
        select(Event, Competitor.name)
        .join(Competitor, Event.competitor_id == Competitor.id)
        .where(
            or_(
                Event.review_status == "pending",
                Event.review_status == "'pending'",
                Event.review_status == '"pending"',
                Event.review_status == "Pending",
            )
        )
    )
    stmt = _apply_non_competitor_name_filters(stmt)
    stmt = (
        stmt.order_by(
            Event.threat_score.desc().nullslast(),
            Event.created_at.desc(),
            Event.id,
        )
        .limit(limit)
    )

    result = await session.execute(stmt)
    rows = result.all()

    items = [_to_dashboard_event_item(event, competitor_name) for event, competitor_name in rows]
    return _dedupe_by_key(items, lambda i: (i["id"],))
