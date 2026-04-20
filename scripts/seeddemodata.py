"""Seed small, idempotent demo data for Milestone 6 dashboard walkthrough."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.competitor import Competitor
from app.models.event import Event
from app.services.scoring_service import assign_traffic_light, calculate_threat_score


@dataclass(frozen=True)
class DemoEventSeed:
    competitor_name: str
    competitor_country: str
    event_type: str
    title: str
    description: str
    event_date: date
    review_status: str
    metadata_json: dict
    threat_score: int | None = None
    traffic_light: str | None = None


def _compute_scores(seed: DemoEventSeed) -> tuple[int, str]:
    """Derive threat_score and traffic_light from seed metadata unless explicitly set."""
    if seed.threat_score is not None and seed.traffic_light is not None:
        return seed.threat_score, seed.traffic_light

    meta = seed.metadata_json or {}
    score = calculate_threat_score(
        event_type=seed.event_type,
        development_stage=meta.get("development_stage"),
        confidence_score=meta.get("confidence_score"),
        region=meta.get("region"),
        country=meta.get("country"),
    )
    return score, assign_traffic_light(score)


# ---------------------------------------------------------------------------
# Demo events for deterministic manager demo (top 5 fixed scores).
# ---------------------------------------------------------------------------

DEMO_EVENTS: list[DemoEventSeed] = [
    DemoEventSeed(
        competitor_name="Amgen",
        competitor_country="United States",
        event_type="clinical_trial_update",
        title="DEMO: Amgen ABP 206 Phase 3 milestone",
        description=(
            "Amgen reported ABP 206 progressed to an advanced Phase 3 milestone "
            "in a nivolumab biosimilar pathway."
        ),
        event_date=date(2026, 4, 18),
        review_status="approved",
        metadata_json={
            "asset_code": "ABP 206",
            "development_stage": "Phase 3",
            "confidence_score": 95,
            "molecule_name": "nivolumab",
            "reference_brand": "Opdivo",
            "drug_name": "Nivolumab (Opdivo)",
            "reference_drug_name": "Nivolumab (Opdivo)",
            "region": "North America",
            "country": "United States",
            "seed_tag": "milestone7_demo_abp206",
        },
        threat_score=95,
        traffic_light="Red",
    ),
    DemoEventSeed(
        competitor_name="Samsung Bioepis",
        competitor_country="South Korea",
        event_type="clinical_trial_update",
        title="DEMO: Samsung Bioepis SB17 advanced trial progress",
        description=(
            "Samsung Bioepis shared SB17 oncology biosimilar trial progression "
            "with accelerated enrollment updates."
        ),
        event_date=date(2026, 4, 16),
        review_status="approved",
        metadata_json={
            "asset_code": "SB17",
            "development_stage": "Phase 3",
            "confidence_score": 82,
            "molecule_name": "nivolumab",
            "reference_brand": "Opdivo",
            "drug_name": "Nivolumab (Opdivo)",
            "reference_drug_name": "Nivolumab (Opdivo)",
            "region": "Asia-Pacific",
            "country": "South Korea",
            "seed_tag": "milestone7_demo_sb17",
        },
        threat_score=82,
        traffic_light="Red",
    ),
    DemoEventSeed(
        competitor_name="Celltrion",
        competitor_country="South Korea",
        event_type="clinical_trial_update",
        title="DEMO: Celltrion CT-P51 Phase 3 signal",
        description=(
            "Celltrion disclosed CT-P51 development update for nivolumab biosimilar "
            "program expansion."
        ),
        event_date=date(2026, 4, 14),
        review_status="approved",
        metadata_json={
            "asset_code": "CT-P51",
            "development_stage": "Phase 2",
            "confidence_score": 74,
            "molecule_name": "nivolumab",
            "reference_brand": "Opdivo",
            "drug_name": "Nivolumab (Opdivo)",
            "reference_drug_name": "Nivolumab (Opdivo)",
            "region": "Asia-Pacific",
            "country": "South Korea",
            "seed_tag": "milestone7_demo_ctp51",
        },
        threat_score=74,
        traffic_light="Amber",
    ),
    DemoEventSeed(
        competitor_name="Fresenius Kabi",
        competitor_country="Germany",
        event_type="press_release_update",
        title="DEMO: Pembrolizumab biosimilar manufacturing expansion",
        description=(
            "Fresenius Kabi announced manufacturing-scale expansion for a "
            "pembrolizumab biosimilar initiative."
        ),
        event_date=date(2026, 4, 10),
        review_status="approved",
        metadata_json={
            "asset_code": "FK-PBRO",
            "development_stage": "Phase 2",
            "confidence_score": 61,
            "molecule_name": "pembrolizumab",
            "reference_brand": "Keytruda",
            "drug_name": "Pembrolizumab (Keytruda)",
            "reference_drug_name": "Pembrolizumab (Keytruda)",
            "region": "Europe",
            "country": "Germany",
            "seed_tag": "milestone7_demo_keytruda",
        },
        threat_score=61,
        traffic_light="Amber",
    ),
    DemoEventSeed(
        competitor_name="Zydus",
        competitor_country="India",
        event_type="regulatory",
        title="DEMO: Zydus ZRC-3197 filing update",
        description="Zydus reported a filing milestone for ZRC-3197 bevacizumab biosimilar program.",
        event_date=date(2026, 4, 8),
        review_status="approved",
        metadata_json={
            "asset_code": "ZRC-3197",
            "development_stage": "Phase 2",
            "confidence_score": 45,
            "molecule_name": "bevacizumab",
            "reference_brand": "Avastin",
            "drug_name": "Bevacizumab (Avastin)",
            "reference_drug_name": "Bevacizumab (Avastin)",
            "region": "Asia-Pacific",
            "country": "India",
            "seed_tag": "milestone7_demo_avastin",
        },
        threat_score=45,
        traffic_light="Green",
    ),
    DemoEventSeed(
        competitor_name="Henlius",
        competitor_country="China",
        event_type="press_release_update",
        title="DEMO: Henlius exploratory preclinical note",
        description="Low-confidence exploratory note retained in pending queue for analyst follow-up.",
        event_date=date(2026, 4, 3),
        review_status="pending",
        metadata_json={
            "asset_code": "HLX-PRELIM",
            "development_stage": "Preclinical",
            "confidence_score": 25,
            "molecule_name": "adalimumab",
            "reference_brand": "Humira",
            "drug_name": "Adalimumab (Humira)",
            "reference_drug_name": "Adalimumab (Humira)",
            "region": "Asia-Pacific",
            "country": "China",
            "seed_tag": "milestone7_demo_pending",
        },
    ),
    DemoEventSeed(
        competitor_name="Henlius",
        competitor_country="China",
        event_type="press_release_update",
        title="DEMO: Henlius unverified rumor",
        description="Unverified secondary-source rumor kept as rejected audit trail sample.",
        event_date=date(2026, 4, 1),
        review_status="rejected",
        metadata_json={
            "asset_code": "HLX-RUMOR",
            "development_stage": None,
            "confidence_score": 10,
            "molecule_name": "adalimumab",
            "reference_brand": "Humira",
            "drug_name": "Adalimumab (Humira)",
            "reference_drug_name": "Adalimumab (Humira)",
            "region": None,
            "country": None,
            "seed_tag": "milestone7_demo_rejected",
        },
    ),
]


async def _get_or_create_competitor(name: str, country: str) -> Competitor:
    async with AsyncSessionLocal() as session:
        stmt = select(Competitor).where(Competitor.name == name)
        result = await session.execute(stmt)
        competitor = result.scalar_one_or_none()

        if competitor is None:
            competitor = Competitor(
                name=name,
                company_type="biosimilar_developer",
                headquarters_country=country,
                is_active=True,
            )
            session.add(competitor)
            await session.commit()
            await session.refresh(competitor)
            return competitor

        competitor.company_type = "biosimilar_developer"
        competitor.headquarters_country = country
        competitor.is_active = True
        await session.commit()
        await session.refresh(competitor)
        return competitor


async def _upsert_event(seed: DemoEventSeed, competitor_id: uuid.UUID) -> str:
    threat_score, traffic_light = _compute_scores(seed)

    async with AsyncSessionLocal() as session:
        stmt = select(Event).where(
            Event.competitor_id == competitor_id,
            Event.title == seed.title,
        )
        result = await session.execute(stmt)
        event = result.scalar_one_or_none()

        if event is None:
            event = Event(
                competitor_id=competitor_id,
                event_type=seed.event_type,
                title=seed.title,
                description=seed.description,
                event_date=seed.event_date,
                threat_score=threat_score,
                traffic_light=traffic_light,
                review_status=seed.review_status,
                metadata_json=seed.metadata_json,
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)
            return "created"

        event.event_type = seed.event_type
        event.description = seed.description
        event.event_date = seed.event_date
        event.threat_score = threat_score
        event.traffic_light = traffic_light
        event.review_status = seed.review_status
        event.metadata_json = seed.metadata_json

        await session.commit()
        return "updated"


async def seed_demo_data() -> None:
    print("Seeding Milestone 6 demo data...")

    competitor_ids: dict[str, uuid.UUID] = {}
    for seed in DEMO_EVENTS:
        competitor = await _get_or_create_competitor(seed.competitor_name, seed.competitor_country)
        competitor_ids[seed.competitor_name] = competitor.id

    created = 0
    updated = 0

    for seed in DEMO_EVENTS:
        score, light = _compute_scores(seed)
        status = await _upsert_event(seed, competitor_ids[seed.competitor_name])
        tag = seed.metadata_json.get("seed_tag", "?")
        if status == "created":
            created += 1
        else:
            updated += 1
        print(f"  [{status}] {seed.title[:60]}  score={score} light={light}")

    print(
        f"Done. events_created={created}, events_updated={updated}, "
        f"total_seed_rows={len(DEMO_EVENTS)}"
    )


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
