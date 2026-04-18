from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.seed_data import SCORING_RULES, SOURCE_METADATA
from app.models.scoring_rule import ScoringRule
from app.models.source import Source


async def _upsert_source(session: AsyncSession, payload: dict) -> None:
    stmt = select(Source).where(Source.key == payload["key"])
    result = await session.execute(stmt)
    source = result.scalar_one_or_none()

    if source is None:
        session.add(Source(**payload))
        return

    for key, value in payload.items():
        setattr(source, key, value)


async def _upsert_scoring_rule(session: AsyncSession, payload: dict) -> None:
    stmt = select(ScoringRule).where(ScoringRule.event_type == payload["event_type"])
    result = await session.execute(stmt)
    rule = result.scalar_one_or_none()

    if rule is None:
        session.add(ScoringRule(**payload))
        return

    for key, value in payload.items():
        setattr(rule, key, value)


async def seed_reference_data(session: AsyncSession) -> None:
    for source_payload in SOURCE_METADATA:
        await _upsert_source(session, source_payload)

    for rule_payload in SCORING_RULES:
        await _upsert_scoring_rule(session, rule_payload)

    await session.commit()
