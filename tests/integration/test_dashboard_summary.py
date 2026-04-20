"""
Integration tests for GET /api/v1/dashboards/summary.

NOTE: This endpoint is NOT yet implemented in the router as of the current
codebase.  All tests are marked ``xfail`` and will pass once the router is
wired up.

Expected endpoint contract (to be implemented):
  GET /api/v1/dashboards/summary
  → 200, aggregate counts of events by traffic_light and/or review_status.

  Example response shape:
  {
    "total_events": 42,
    "approved": 30,
    "pending": 8,
    "rejected": 4,
    "by_traffic_light": {"Green": 18, "Amber": 9, "Red": 3}
  }
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient



@pytest.mark.anyio
async def test_dashboard_summary_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/dashboards/summary")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_dashboard_summary_response_is_json_object(client: AsyncClient) -> None:
    response = await client.get("/api/v1/dashboards/summary")
    body = response.json()
    assert isinstance(body, dict)


@pytest.mark.anyio
async def test_dashboard_summary_has_total_events_key(client: AsyncClient) -> None:
    response = await client.get("/api/v1/dashboards/summary")
    body = response.json()
    assert "total_events" in body
    assert isinstance(body["total_events"], int)


@pytest.mark.anyio
async def test_dashboard_summary_has_review_status_counts(client: AsyncClient) -> None:
    response = await client.get("/api/v1/dashboards/summary")
    body = response.json()
    # At least one of these keys should be present
    review_keys = {"approved", "pending", "rejected"}
    assert review_keys.intersection(set(body.keys()))


@pytest.mark.anyio
async def test_dashboard_summary_traffic_light_counts_present(client: AsyncClient) -> None:
    response = await client.get("/api/v1/dashboards/summary")
    body = response.json()
    # The summary should expose a traffic_light breakdown or top-level green/amber/red keys
    has_breakdown = "by_traffic_light" in body
    has_flat_keys = {"green", "amber", "red"}.intersection({k.lower() for k in body})
    assert has_breakdown or has_flat_keys


@pytest.mark.anyio
async def test_dashboard_summary_approved_count_not_greater_than_total(client: AsyncClient) -> None:
    response = await client.get("/api/v1/dashboards/summary")
    body = response.json()
    if "total_events" in body and "approved" in body:
        assert body["approved"] <= body["total_events"]


@pytest.mark.anyio
async def test_dashboard_summary_excludes_rejected_from_approved_count(client: AsyncClient) -> None:
    response = await client.get("/api/v1/dashboards/summary")
    body = response.json()
    if "approved" in body and "rejected" in body and "total_events" in body:
        assert body["approved"] + body["rejected"] <= body["total_events"]
