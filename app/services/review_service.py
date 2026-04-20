"""Review / approval workflow service backed by SQLAlchemy persistence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.review import Review
from app.schemas.review import ReviewCreate, ReviewRead

VALID_REVIEW_STATUSES = {"pending", "approved", "rejected"}


def _safe_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None


def _normalize_status(status: str | None) -> str:
    normalized = (status or "").strip().lower()
    if normalized in VALID_REVIEW_STATUSES:
        return normalized
    return "pending"


def _to_review_read(review: Review) -> ReviewRead:
    return ReviewRead(
        id=review.id,
        event_id=review.event_id,
        status=review.status,
        reviewer=review.reviewer,
        review_notes=review.review_notes,
        review_status=review.status,
        created_at=review.created_at,
    )


async def _get_event_by_id(session: AsyncSession, event_id: str) -> Event | None:
    parsed_id = _safe_uuid(event_id)
    if parsed_id is None:
        return None

    result = await session.execute(select(Event).where(Event.id == parsed_id))
    return result.scalar_one_or_none()


async def approve_event(
    session: AsyncSession,
    event_id: str,
    reviewer_email: str | None = None,
    comment: str | None = None,
) -> ReviewRead | None:
    event = await _get_event_by_id(session, event_id)
    if event is None:
        return None

    review = Review(
        event_id=event.id,
        status="approved",
        reviewer=reviewer_email,
        review_notes=comment,
        reviewed_at=datetime.now(UTC),
    )
    event.review_status = "approved"

    session.add(review)
    await session.commit()
    await session.refresh(review)
    return _to_review_read(review)


async def reject_event(
    session: AsyncSession,
    event_id: str,
    reviewer_email: str | None = None,
    comment: str | None = None,
) -> ReviewRead | None:
    event = await _get_event_by_id(session, event_id)
    if event is None:
        return None

    review = Review(
        event_id=event.id,
        status="rejected",
        reviewer=reviewer_email,
        review_notes=comment,
        reviewed_at=datetime.now(UTC),
    )
    event.review_status = "rejected"

    session.add(review)
    await session.commit()
    await session.refresh(review)
    return _to_review_read(review)


async def create_review(session: AsyncSession, data: ReviewCreate) -> ReviewRead | None:
    event_id = str(data.event_id)
    event = await _get_event_by_id(session, event_id)
    if event is None:
        return None

    normalized_status = _normalize_status(data.status)

    review = Review(
        event_id=event.id,
        status=normalized_status,
        reviewer=data.reviewer,
        review_notes=data.review_notes,
        reviewed_at=datetime.now(UTC),
    )
    event.review_status = normalized_status

    session.add(review)
    await session.commit()
    await session.refresh(review)
    return _to_review_read(review)


async def list_reviews(session: AsyncSession) -> list[ReviewRead]:
    """Return persisted review rows, newest first."""
    stmt = select(Review).order_by(Review.created_at.desc())
    result = await session.execute(stmt)
    reviews = list(result.scalars().all())
    return [_to_review_read(review) for review in reviews]
