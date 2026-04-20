"""Events CRUD router – /api/v1/events."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.event import EventCreate, EventRead, EventUpdate
from app.services import event_service

router = APIRouter(prefix="/events", tags=["Events"])


@router.post("", response_model=EventRead, status_code=201)
async def create_event(
    payload: EventCreate,
    db: AsyncSession = Depends(get_db),
) -> EventRead:
    return await event_service.create_event(db, payload)


@router.get("", response_model=list[EventRead])
async def list_events(
    traffic_light: str | None = None,
    event_type: str | None = None,
    region: str | None = None,
    country: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[EventRead]:
    return await event_service.list_events(
        db,
        traffic_light=traffic_light,
        event_type=event_type,
        region=region,
        country=country,
    )


@router.get("/{event_id}", response_model=EventRead)
async def get_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> EventRead:
    event = await event_service.get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.patch("/{event_id}", response_model=EventRead)
async def update_event(
    event_id: str,
    payload: EventUpdate,
    db: AsyncSession = Depends(get_db),
) -> EventRead:
    event = await event_service.update_event(db, event_id, payload)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
