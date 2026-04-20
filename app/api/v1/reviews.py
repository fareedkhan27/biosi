"""Reviews router – approve/reject workflow + direct review creation."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.review import ApproveRejectRequest, ReviewCreate, ReviewRead
from app.services import review_service

router = APIRouter(tags=["Reviews"])


@router.get("/reviews", response_model=list[ReviewRead])
async def list_reviews(
    db: AsyncSession = Depends(get_db),
) -> list[ReviewRead]:
    return await review_service.list_reviews(db)


@router.post("/events/{event_id}/approve", response_model=ReviewRead)
async def approve_event(
    event_id: str,
    payload: ApproveRejectRequest = Body(default_factory=ApproveRejectRequest),
    db: AsyncSession = Depends(get_db),
) -> ReviewRead:
    result = await review_service.approve_event(
        db, event_id, reviewer_email=payload.reviewer_email, comment=payload.comment
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.post("/events/{event_id}/reject", response_model=ReviewRead)
async def reject_event(
    event_id: str,
    payload: ApproveRejectRequest = Body(default_factory=ApproveRejectRequest),
    db: AsyncSession = Depends(get_db),
) -> ReviewRead:
    result = await review_service.reject_event(
        db, event_id, reviewer_email=payload.reviewer_email, comment=payload.comment
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.post("/reviews", response_model=ReviewRead, status_code=201)
async def create_review(
    payload: ReviewCreate,
    db: AsyncSession = Depends(get_db),
) -> ReviewRead:
    result = await review_service.create_review(db, payload)
    if result is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return result
