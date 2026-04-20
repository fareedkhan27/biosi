"""Purge stale event/review data and re-ingest fresh ClinicalTrials events.

Run with:
  python -m scripts.purge_and_reingest
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
from sqlalchemy import delete, func, select

from app.db.session import AsyncSessionLocal
from app.models.event import Event
from app.models.review import Review

API_BASE_URL = os.getenv("BIOSI_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
INGEST_URL = f"{API_BASE_URL}/api/v1/jobs/ingest/clinicaltrials"
TOP_THREATS_URL = f"{API_BASE_URL}/api/v1/dashboards/top-threats?limit=10"


async def _count_rows() -> tuple[int, int]:
    """Return (event_count, review_count)."""
    async with AsyncSessionLocal() as session:
        event_count_result = await session.execute(select(func.count(Event.id)))
        review_count_result = await session.execute(select(func.count(Review.id)))

        event_count = int(event_count_result.scalar_one() or 0)
        review_count = int(review_count_result.scalar_one() or 0)
        return event_count, review_count


async def _purge_events_and_reviews() -> tuple[int, int]:
    """Delete reviews first, then events. Returns (events_purged, reviews_purged)."""
    before_events, before_reviews = await _count_rows()

    print(f"Before purge: events={before_events}, reviews={before_reviews}")

    async with AsyncSessionLocal() as session:
        await session.execute(delete(Review))
        await session.execute(delete(Event))
        await session.commit()

    after_events, after_reviews = await _count_rows()
    print(f"After purge:  events={after_events}, reviews={after_reviews}")

    purged_events = max(0, before_events - after_events)
    purged_reviews = max(0, before_reviews - after_reviews)

    return purged_events, purged_reviews


async def _trigger_reingestion() -> dict[str, Any] | list[Any] | str:
    """Trigger ClinicalTrials ingestion job and return parsed response body."""
    timeout = httpx.Timeout(300.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(INGEST_URL)
            response.raise_for_status()
            try:
                return response.json()
            except ValueError:
                return response.text
    except httpx.ConnectError:
        print(f"ERROR: Could not connect to {API_BASE_URL}. Is uvicorn running?")
        raise
    except httpx.TimeoutException:
        print("ERROR: Ingestion request timed out after 300 seconds.")
        raise
    except httpx.HTTPStatusError as exc:
        print(
            "ERROR: Ingestion endpoint returned "
            f"status={exc.response.status_code}, body={exc.response.text}"
        )
        raise


async def _print_top_threats() -> None:
    """Fetch and print top-threat rows in the requested format."""
    timeout = httpx.Timeout(60.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(TOP_THREATS_URL)
            response.raise_for_status()
            payload = response.json()
    except httpx.ConnectError:
        print(f"ERROR: Could not connect to {API_BASE_URL}. Is uvicorn running?")
        raise
    except httpx.TimeoutException:
        print("ERROR: Top-threats request timed out.")
        raise
    except httpx.HTTPStatusError as exc:
        print(
            "ERROR: Top-threats endpoint returned "
            f"status={exc.response.status_code}, body={exc.response.text}"
        )
        raise

    if not isinstance(payload, list):
        print(f"Unexpected top-threats response (not a list): {payload}")
        return

    if not payload:
        print("Top threats: no rows returned.")
        return

    for item in payload:
        if not isinstance(item, dict):
            print(f"Unexpected row format: {item}")
            continue

        competitor_name = item.get("competitor_name")
        drug_name = item.get("drug_name")
        indication = item.get("indication")
        threat_score = item.get("threat_score")
        traffic_light = item.get("traffic_light")
        country = item.get("country")

        print(
            f"{competitor_name} | {drug_name} | {indication} | "
            f"{threat_score} | {traffic_light} | {country}"
        )


async def _run() -> None:
    purged_events, purged_reviews = await _purge_events_and_reviews()
    print(f"✓ Purged {purged_events} events and {purged_reviews} reviews from database")

    ingestion_result = await _trigger_reingestion()
    print("Ingestion response JSON:")
    print(ingestion_result)

    print("Top threats:")
    await _print_top_threats()

    print('Run with: python -m scripts.purge_and_reingest')
    print('Make sure uvicorn is running before executing this script.')


def main() -> None:
    try:
        asyncio.run(_run())
    except Exception:
        # Errors are already printed with clear messages in helper functions.
        pass


if __name__ == "__main__":
    main()
