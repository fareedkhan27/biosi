"""Deterministic interpretation layer for scored biosimilar events."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competitor import Competitor
from app.models.event import Event
from app.services.dashboard_service import _apply_non_competitor_name_filters, _normalize_review_status

_GEO_CONTEXT = {
    "india": "market open (LOE expired)",
    "united states": "approaching LOE window (~2028)",
    "us": "approaching LOE window (~2028)",
    "usa": "approaching LOE window (~2028)",
    "eu": "medium-term LOE (~2029–2030)",
    "europe": "medium-term LOE (~2029–2030)",
    "european union": "medium-term LOE (~2029–2030)",
}
_PRIMARY_INDICATIONS = {"nsclc", "melanoma"}
_SECONDARY_INDICATIONS = {"rcc", "scchn"}


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None


def _normalized(value: Any) -> str | None:
    cleaned = _text(value)
    if cleaned is None:
        return None
    return cleaned.lower()


def _event_metadata(event: Event) -> dict[str, Any]:
    metadata = getattr(event, "metadata_json", None)
    if isinstance(metadata, dict):
        return metadata
    return {}


def _score_breakdown(event: Event) -> dict[str, Any]:
    breakdown = _event_metadata(event).get("score_breakdown")
    if isinstance(breakdown, dict):
        return breakdown
    return {}


def _event_competitor_name(event: Event) -> str:
    transient_name = _text(getattr(event, "_intelligence_competitor_name", None))
    if transient_name is not None:
        return transient_name

    competitor = getattr(event, "competitor", None)
    competitor_name = _text(getattr(competitor, "name", None))
    if competitor_name is not None:
        return competitor_name

    metadata_name = _text(_event_metadata(event).get("competitor_name"))
    if metadata_name is not None:
        return metadata_name
    return "Unknown competitor"


def _event_stage(event: Event) -> str | None:
    metadata = _event_metadata(event)
    return _text(metadata.get("development_stage"))


def _event_indication(event: Event) -> str | None:
    indication = _text(getattr(event, "indication", None))
    if indication is not None:
        return indication
    return _text(_event_metadata(event).get("indication"))


def _event_country(event: Event) -> str | None:
    return _text(_event_metadata(event).get("country"))


def _event_region(event: Event) -> str | None:
    return _text(_event_metadata(event).get("region"))


def _event_competitor_tier(event: Event) -> int | None:
    value = _event_metadata(event).get("competitor_tier")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _event_score(event: Event) -> int:
    score = getattr(event, "threat_score", None)
    if isinstance(score, int):
        return score
    if isinstance(score, float):
        return int(score)
    return 0


def _event_traffic_light(event: Event) -> str | None:
    value = _text(getattr(event, "traffic_light", None))
    if value is None:
        return None
    cleaned = value.strip("\"'").strip().lower()
    canonical = cleaned.capitalize()
    if canonical in {"Green", "Amber", "Red"}:
        return canonical
    return None


def _event_created_rank(event: Event) -> str:
    created_at = getattr(event, "created_at", None)
    if isinstance(created_at, datetime):
        return created_at.isoformat()
    return ""


def _normalize_stage_key(stage: str | None) -> str | None:
    stage_normalized = _normalized(stage)
    if stage_normalized is None:
        return None
    compact = stage_normalized.replace("-", " ").replace("_", " ")
    if "phase 3" in compact:
        return "phase_3"
    if "phase 2" in compact:
        return "phase_2"
    if "phase 1" in compact:
        return "phase_1"
    if "phase 4" in compact:
        return "phase_4"
    if compact in {"launch", "market", "market launch", "approval", "approved"}:
        return "launch"
    if compact == "ind":
        return "ind"
    return compact.replace(" ", "_")


def _display_stage(stage: str | None) -> str:
    stage_text = _text(stage)
    if stage_text is None:
        return "development"
    return stage_text.lower().replace("_", " ")


def _display_indication(indication: str | None) -> str:
    indication_text = _text(indication)
    if indication_text is None:
        return "the lead indication"
    return indication_text


def _location_text(event: Event) -> str | None:
    country = _event_country(event)
    if country is not None:
        return country
    return _event_region(event)


def _geo_context(event: Event) -> str | None:
    country = _normalized(_event_country(event))
    if country is not None and country in _GEO_CONTEXT:
        return _GEO_CONTEXT[country]

    region = _normalized(_event_region(event))
    if region is not None and region in _GEO_CONTEXT:
        return _GEO_CONTEXT[region]
    return None


def _indication_context(event: Event) -> str | None:
    indication = _normalized(_event_indication(event))
    if indication in _PRIMARY_INDICATIONS:
        return "primary extrapolation anchor"
    if indication in _SECONDARY_INDICATIONS:
        return "secondary extrapolation risk"
    return None


def _build_confidence_note(event: Event) -> str | None:
    breakdown = _score_breakdown(event)
    raw_flags = breakdown.get("flags")
    flags = [flag for flag in raw_flags if isinstance(flag, str)] if isinstance(raw_flags, list) else []
    if flags:
        normalized_flags = ", ".join(flag.replace("_", " ") for flag in flags)
        return f"Interpret with caution: {normalized_flags}."

    confidence_component = breakdown.get("confidence")
    if isinstance(confidence_component, int):
        if confidence_component >= 4:
            return "High-confidence source signal."
        if confidence_component <= 2:
            return "Lower-confidence signal; corroborate with follow-up updates."
    return None


def _append_context(summary: str, event: Event) -> str:
    additions: list[str] = []
    geo_context = _geo_context(event)
    if geo_context is not None:
        additions.append(geo_context)

    indication_context = _indication_context(event)
    if indication_context is not None:
        additions.append(indication_context)

    if not additions:
        return summary
    return f"{summary}; {'; '.join(additions)}"


def _tier_insight(event: Event) -> str | None:
    tier = _event_competitor_tier(event)
    if tier is None:
        return None
    if tier == 1:
        return "tier-1 competitor profile"
    if tier == 2:
        return "tier-2 competitor profile"
    if tier >= 3:
        return "lower-tier competitor profile"
    return None


def _stage_insight(event: Event) -> str | None:
    stage_key = _normalize_stage_key(_event_stage(event))
    if stage_key in {"launch", "phase_4", "phase_3"}:
        return "late-stage development signal"
    if stage_key in {"phase_2", "ind"}:
        return "mid-stage pipeline signal"
    if stage_key in {"phase_1"}:
        return "early-stage pipeline signal"
    return None


def _geography_insight(event: Event) -> str | None:
    geo_context = _geo_context(event)
    if geo_context is not None:
        return geo_context

    location = _location_text(event)
    if location is not None:
        return f"active in {location}"
    return None


def _indication_insight(event: Event) -> str | None:
    indication_context = _indication_context(event)
    indication = _event_indication(event)
    if indication_context is not None:
        return indication_context
    if indication is not None:
        return f"targeting {indication}"
    return None


def _dynamic_risk_reason(event: Event, score: int) -> str:
    factors: list[str] = []
    tier_reason = _tier_insight(event)
    if tier_reason is not None:
        factors.append(tier_reason)

    stage_reason = _stage_insight(event)
    if stage_reason is not None:
        factors.append(stage_reason)

    geography_reason = _geography_insight(event)
    if geography_reason is not None:
        factors.append(geography_reason)

    indication_reason = _indication_insight(event)
    if indication_reason is not None:
        factors.append(indication_reason)

    if not factors:
        if score >= 75:
            return "High overall threat score with limited enrichment context"
        if score >= 45:
            return "Moderate threat score with partial enrichment context"
        return "Low threat score with limited immediate commercial signal"

    top_factors = ", ".join(factors[:3])
    return f"Score drivers: {top_factors}"


def _recommended_action(event: Event, score: int) -> str | None:
    stage_reason = _stage_insight(event)
    indication_reason = _indication_insight(event)
    if score >= 75:
        if stage_reason == "late-stage development signal":
            return "Prepare indication-specific defense plan; monitor regulatory milestones"
        return "Review near-term milestones; validate commercial exposure"
    if score >= 45:
        if indication_reason is not None:
            return "Track progression; validate indication overlap"
        return "Track progression and complete indication/geography enrichment"
    return None


def _risk_bucket_phrase(score: int) -> str:
    if score >= 75:
        return "high competitive pressure"
    if score >= 45:
        return "potential competitive pressure"
    return "low immediate risk"


def build_event_insight(event: Event) -> dict[str, str | None]:
    """Build a deterministic, decision-ready interpretation for a scored event."""

    competitor = _event_competitor_name(event)
    stage = _event_stage(event)
    stage_display = _display_stage(stage)
    indication = _event_indication(event)
    indication_display = _display_indication(indication)
    location = _location_text(event)
    location_fragment = f" ({location})" if location is not None else ""
    score = _event_score(event)

    if score >= 45:
        summary = (
            f"{competitor} progressing {stage_display} in {indication_display}{location_fragment} — "
            f"{_risk_bucket_phrase(score)}"
        )
    else:
        summary = f"Early-stage activity from {competitor} — low immediate risk"

    risk_reason = _dynamic_risk_reason(event, score)
    recommended_action = _recommended_action(event, score)

    return {
        "summary": _append_context(summary, event),
        "risk_reason": risk_reason,
        "recommended_action": recommended_action,
        "confidence_note": _build_confidence_note(event),
    }


def build_competitor_summary(events: list[Event]) -> dict[str, Any]:
    """Summarize the highest-priority signal for a single competitor."""

    if not events:
        raise ValueError("build_competitor_summary requires at least one event")

    ranked_events = sorted(
        events,
        key=lambda event: (
            _event_score(event),
            _event_created_rank(event),
        ),
        reverse=True,
    )
    top_event = ranked_events[0]
    insight = build_event_insight(top_event)
    event_count = len(events)

    support_text = (
        f"Supported by {event_count} events in the current digest."
        if event_count > 1
        else "Supported by 1 event in the current digest."
    )

    return {
        "competitor_name": _event_competitor_name(top_event),
        "event_count": event_count,
        "max_score": _event_score(top_event),
        "top_indication": _event_indication(top_event) or "Unknown",
        "summary": f"{insight['summary']} {support_text}",
    }


def _serialize_event(event: Event) -> dict[str, Any]:
    try:
        insight = build_event_insight(event)
    except Exception:
        insight = {
            "summary": None,
            "risk_reason": None,
            "recommended_action": None,
            "confidence_note": None,
        }
    metadata = _event_metadata(event)
    return {
        "id": str(event.id),
        "competitor_id": str(event.competitor_id),
        "competitor_name": _event_competitor_name(event),
        "event_type": event.event_type,
        "title": event.title,
        "event_date": event.event_date.isoformat() if event.event_date is not None else None,
        "created_at": event.created_at.isoformat() if event.created_at is not None else None,
        "review_status": _normalize_review_status(getattr(event, "review_status", "pending")),
        "threat_score": _event_score(event),
        "traffic_light": _event_traffic_light(event),
        "development_stage": _event_stage(event),
        "indication": _event_indication(event),
        "country": _event_country(event),
        "region": _event_region(event),
        "competitor_tier": _event_competitor_tier(event),
        "estimated_launch_year": metadata.get("estimated_launch_year"),
        "score_breakdown": _score_breakdown(event) or None,
        **insight,
    }


async def build_weekly_digest(
    session: AsyncSession,
    *,
    limit: int = 100,
    approved_only: bool = False,
) -> dict[str, Any]:
    """Return additive intelligence digest payload for scored events."""

    stmt = (
        select(Event, Competitor.name)
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

    top_insights: list[dict[str, Any]] = []
    grouped_events: dict[str, list[Event]] = defaultdict(list)
    counts = {"red": 0, "amber": 0, "green": 0}

    for event, competitor_name in rows:
        normalized_status = _normalize_review_status(getattr(event, "review_status", None))
        if normalized_status == "rejected":
            continue
        setattr(event, "_intelligence_competitor_name", competitor_name)
        top_insights.append(_serialize_event(event))

        traffic_light = _event_traffic_light(event)
        if traffic_light == "Red":
            counts["red"] += 1
        elif traffic_light == "Amber":
            counts["amber"] += 1
        else:
            counts["green"] += 1

        grouped_events[competitor_name or str(event.competitor_id)].append(event)

    competitor_summary = [
        build_competitor_summary(events)
        for events in grouped_events.values()
    ]
    competitor_summary.sort(key=lambda item: item["max_score"], reverse=True)

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "top_insights": top_insights,
        "competitor_summary": competitor_summary,
        "counts": counts,
    }


# ---------------------------------------------------------------------------
# Department-specific intelligence briefings
# ---------------------------------------------------------------------------

_DEPARTMENT_LENSES: dict[str, str] = {
    "regulatory": "Regulatory lens: prioritise approval pathways, filing timelines, and agency interactions.",
    "commercial": "Commercial lens: prioritise market sizing, launch timing, and competitive share impact.",
    "medical_affairs": "Medical Affairs lens: prioritise clinical evidence, indication expansion, and KOL sentiment.",
    "market_access": "Market Access lens: prioritise reimbursement status, pricing pressure, and formulary positioning.",
}

_VALID_DEPARTMENTS = set(_DEPARTMENT_LENSES.keys())


def _department_frame(event: Event, department: str) -> str:
    """Re-frame a single event insight for a specific department."""
    insight = build_event_insight(event)
    base_summary = insight.get("summary") or "No summary available"
    score = _event_score(event)
    stage = _event_stage(event) or "unknown stage"
    indication = _event_indication(event) or "unknown indication"
    country = _event_country(event) or "unknown geography"

    if department == "regulatory":
        if score >= 75:
            return (
                f"High-priority regulatory signal: {base_summary}. "
                f"Monitor {stage} progression in {country} for accelerated-review eligibility."
            )
        return (
            f"Regulatory watch: {base_summary}. Track {stage} milestones in {country}."
        )

    if department == "commercial":
        if score >= 75:
            return (
                f"Near-term commercial threat: {base_summary}. "
                f"Assess revenue-at-risk in {country} and prepare launch-readiness response."
            )
        return (
            f"Commercial monitor: {base_summary}. Evaluate {indication} overlap and timing."
        )

    if department == "medical_affairs":
        if score >= 75:
            return (
                f"High-impact clinical signal: {base_summary}. "
                f"Engage KOLs in {country} and prepare scientific narrative for {indication}."
            )
        return (
            f"Clinical pipeline watch: {base_summary}. Track evidence generation for {indication}."
        )

    if department == "market_access":
        if score >= 75:
            return (
                f"Urgent access risk: {base_summary}. "
                f"Evaluate pricing and reimbursement implications in {country}."
            )
        return (
            f"Access landscape monitor: {base_summary}. Review HTA pathway in {country}."
        )

    return base_summary


def _build_market_sections(
    events: list[Event],
    department: str,
) -> list[dict[str, str]]:
    """Generate department-specific market sections from a set of events."""
    if not events:
        return []

    red_count = sum(1 for e in events if _event_traffic_light(e) == "Red")
    amber_count = sum(1 for e in events if _event_traffic_light(e) == "Amber")
    high_score_events = [e for e in events if _event_score(e) >= 75]

    sections: list[dict[str, str]] = []

    if department == "regulatory":
        sections.append({
            "section_title": "Regulatory Pipeline Overview",
            "body": (
                f"{red_count} late-stage signals require immediate regulatory surveillance. "
                f"{amber_count} mid-stage programs are in active watch. "
                f"Focus agency engagement on the top {len(high_score_events)} high-threat competitors."
            ),
            "priority": "high" if red_count > 0 else "medium",
        })

    elif department == "commercial":
        sections.append({
            "section_title": "Competitive Landscape Summary",
            "body": (
                f"{red_count} near-term competitive entries pose direct revenue risk. "
                f"{amber_count} emerging threats are tracking toward launch windows. "
                f"Recommend scenario planning for the {len(high_score_events)} highest-priority signals."
            ),
            "priority": "high" if red_count > 0 else "medium",
        })

    elif department == "medical_affairs":
        sections.append({
            "section_title": "Clinical Evidence & KOL Landscape",
            "body": (
                f"{red_count} high-priority clinical signals require scientific narrative preparation. "
                f"{amber_count} mid-priority studies are generating data that may shift KOL sentiment. "
                f"Advisory board planning recommended for the {len(high_score_events)} top threats."
            ),
            "priority": "high" if red_count > 0 else "medium",
        })

    elif department == "market_access":
        sections.append({
            "section_title": "Access & Reimbursement Risk Summary",
            "body": (
                f"{red_count} high-priority signals indicate imminent pricing pressure. "
                f"{amber_count} mid-term threats may reshape formulary positioning. "
                f"HTA and payer engagement recommended for the {len(high_score_events)} top threats."
            ),
            "priority": "high" if red_count > 0 else "medium",
        })

    return sections


def _build_milestones(events: list[Event]) -> list[dict[str, str | None]]:
    """Extract upcoming milestone-like events sorted by date."""
    scored_events = sorted(
        [e for e in events if e.event_date is not None and _event_score(e) >= 45],
        key=lambda e: (e.event_date, _event_score(e)),
        reverse=False,
    )

    milestones: list[dict[str, str | None]] = []
    for event in scored_events[:10]:
        stage = _event_stage(event)
        m_type = "milestone"
        if stage in {"launch", "approval", "approved", "market"}:
            m_type = "launch/approval"
        elif "phase 3" in (stage or "").lower():
            m_type = "phase_3"
        elif "phase 2" in (stage or "").lower():
            m_type = "phase_2"

        milestones.append({
            "date": event.event_date.isoformat() if event.event_date else None,
            "competitor_name": _event_competitor_name(event),
            "title": event.title,
            "milestone_type": m_type,
            "priority": "high" if _event_score(event) >= 75 else "medium",
        })

    return milestones


def _build_executive_summary(
    events: list[Event],
    department: str,
) -> str:
    """Generate a one-paragraph executive summary tailored to the department."""
    if not events:
        return f"No competitive signals require attention for the {department} team this period."

    red_count = sum(1 for e in events if _event_traffic_light(e) == "Red")
    top_competitor = ""
    top_score = 0
    for e in events:
        s = _event_score(e)
        if s > top_score:
            top_score = s
            top_competitor = _event_competitor_name(e)

    lens = _DEPARTMENT_LENSES.get(department, "")

    if red_count == 0:
        return (
            f"{lens} No immediate high-priority threats identified. "
            f"Monitor pipeline activity from {top_competitor or 'key competitors'} and maintain readiness."
        )

    return (
        f"{lens} {red_count} high-priority signal(s) detected, led by {top_competitor} "
        f"(threat score {top_score}). Immediate department action is recommended."
    )


async def build_department_briefing(
    session: AsyncSession,
    department: str,
    *,
    limit: int = 50,
    approved_only: bool = False,
) -> dict[str, Any]:
    """Return a structured, department-specific intelligence briefing."""

    if department not in _VALID_DEPARTMENTS:
        raise ValueError(
            f"Invalid department '{department}'. Valid: {', '.join(sorted(_VALID_DEPARTMENTS))}"
        )

    stmt = (
        select(Event, Competitor.name)
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
        Event.event_date.desc().nullslast(),
        Event.id,
    ).limit(limit)

    result = await session.execute(stmt)
    rows = result.all()

    events: list[Event] = []
    for event, competitor_name in rows:
        setattr(event, "_intelligence_competitor_name", competitor_name)
        events.append(event)

    event_cards: list[dict[str, Any]] = []
    for event in events:
        insight = build_event_insight(event)
        event_cards.append({
            "id": str(event.id),
            "competitor_name": _event_competitor_name(event),
            "title": event.title,
            "threat_score": _event_score(event),
            "traffic_light": _event_traffic_light(event) or "Green",
            "department_frame": _department_frame(event, department),
            "recommended_action": insight.get("recommended_action"),
            "event_date": event.event_date.isoformat() if event.event_date else None,
        })

    return {
        "department": department,
        "generated_at": datetime.now().astimezone().isoformat(),
        "executive_summary": _build_executive_summary(events, department),
        "market_sections": _build_market_sections(events, department),
        "event_cards": event_cards,
        "milestones": _build_milestones(events),
    }
