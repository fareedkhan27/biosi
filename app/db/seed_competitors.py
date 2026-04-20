from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.biosimilar_competitor import BiosimilarCompetitor
from app.models.competitor import Competitor

COMPETITOR_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "name": "Amgen",
        "tier": 1,
        "geography": "US, EU",
        "asset_name": "ABP 206",
        "stage": "Phase 3 complete",
        "est_launch_year": 2028,
    },
    {
        "name": "Zydus Lifesciences",
        "tier": 1,
        "geography": "India",
        "asset_name": "Tishtha",
        "stage": "Launched Jan 2026",
        "est_launch_year": 2026,
    },
    {
        "name": "Xbrane / Intas",
        "tier": 2,
        "geography": "US, EU",
        "asset_name": "Xdivane",
        "stage": "Phase 1/3 active",
        "est_launch_year": 2028,
    },
    {
        "name": "Boan Biotech",
        "tier": 2,
        "geography": "China",
        "asset_name": "BA1104",
        "stage": "Phase 3 enrolment complete",
        "est_launch_year": 2027,
    },
    {
        "name": "Sandoz",
        "tier": 2,
        "geography": "US, EU",
        "asset_name": "JPB898",
        "stage": "Phase 3 suspended/restarting",
        "est_launch_year": 2029,
    },
    {
        "name": "Henlius",
        "tier": 3,
        "geography": "Global",
        "asset_name": "HLX18",
        "stage": "IND stage",
        "est_launch_year": 2029,
    },
    {
        "name": "mAbxience",
        "tier": 3,
        "geography": "EU, Global",
        "asset_name": "MB11",
        "stage": "Phase 3 registered",
        "est_launch_year": 2029,
    },
    {
        "name": "Reliance Life Sciences",
        "tier": 3,
        "geography": "India",
        "asset_name": "R-TPR-067",
        "stage": "Phase 1/3 approved",
        "est_launch_year": 2027,
    },
    {
        "name": "Enzene",
        "tier": 3,
        "geography": "India",
        "asset_name": None,
        "stage": "Phase 3 pending revision",
        "est_launch_year": 2027,
    },
    {
        "name": "Dr. Reddy's",
        "tier": 4,
        "geography": "India, Global",
        "asset_name": None,
        "stage": "Pre-clinical",
        "est_launch_year": 2030,
    },
    {
        "name": "Biocon Biologics",
        "tier": 4,
        "geography": "India, Global",
        "asset_name": None,
        "stage": "Pre-clinical",
        "est_launch_year": 2030,
    },
    {
        "name": "NeuClone",
        "tier": 4,
        "geography": "Global",
        "asset_name": None,
        "stage": "Pre-clinical",
        "est_launch_year": 2031,
    },
)


def _default_headquarters_country(geography: str) -> str | None:
    if "," in geography or geography.strip().lower() == "global":
        return None
    return geography.strip() or None


async def _upsert_competitor(session: AsyncSession, payload: dict[str, Any]) -> Competitor:
    stmt = select(Competitor).where(Competitor.name == payload["name"])
    result = await session.execute(stmt)
    competitor = result.scalar_one_or_none()

    headquarters_country = _default_headquarters_country(payload["geography"])
    if competitor is None:
        competitor = Competitor(
            name=payload["name"],
            company_type="biosimilar_developer",
            headquarters_country=headquarters_country,
            is_active=True,
        )
        session.add(competitor)
        await session.flush()
        return competitor

    competitor.company_type = "biosimilar_developer"
    competitor.is_active = True
    if competitor.headquarters_country is None and headquarters_country is not None:
        competitor.headquarters_country = headquarters_country
    await session.flush()
    return competitor


async def _upsert_profile(
    session: AsyncSession,
    competitor: Competitor,
    payload: dict[str, Any],
) -> None:
    stmt = select(BiosimilarCompetitor).where(BiosimilarCompetitor.name == payload["name"])
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()

    values = {
        "competitor_id": competitor.id,
        "name": payload["name"],
        "tier": payload["tier"],
        "geography": payload["geography"],
        "asset_name": payload["asset_name"],
        "stage": payload["stage"],
        "est_launch_year": payload["est_launch_year"],
    }

    if profile is None:
        session.add(BiosimilarCompetitor(**values))
        return

    for key, value in values.items():
        setattr(profile, key, value)


async def seed_competitor_profiles(session: AsyncSession) -> None:
    for payload in COMPETITOR_PROFILES:
        competitor = await _upsert_competitor(session, payload)
        await _upsert_profile(session, competitor, payload)

    await session.commit()


async def run_seed_competitors() -> None:
    async with AsyncSessionLocal() as session:
        await seed_competitor_profiles(session)


if __name__ == "__main__":
    asyncio.run(run_seed_competitors())
