"""Thin integration tests using FastAPI TestClient against the configured database."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


@pytest.fixture(scope="session", autouse=True)
def ensure_seeded_data() -> None:
    """Ensure baseline reference + demo data exists before API integration tests."""

    project_root = Path(__file__).resolve().parents[1]
    python = project_root / ".venv" / "bin" / "python"

    env = os.environ.copy()
    env.setdefault("APP_ENV", "test")

    subprocess.run(
        [str(python), "-m", "app.db.seed"],
        cwd=project_root,
        check=True,
        env=env,
    )
    subprocess.run(
        [str(python), "-m", "scripts.seeddemodata"],
        cwd=project_root,
        check=True,
        env=env,
    )


@pytest.fixture(scope="session")
def test_client() -> TestClient:
    from app.main import app

    with TestClient(app) as client:
        yield client


def _get_any_competitor_id(test_client: TestClient) -> str:
    events = test_client.get("/api/v1/events")
    assert events.status_code == 200
    items = events.json()
    assert isinstance(items, list) and items
    return items[0]["competitor_id"]


def test_health_returns_ok_status(test_client: TestClient) -> None:
    response = test_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_n8n_returns_expected_shape(test_client: TestClient) -> None:
    response = test_client.get("/api/v1/health/n8n")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"status", "db", "openrouter", "version", "timestamp"}
    assert body["status"] == "ok"
    assert body["db"] == "connected"


def test_events_list_and_detail(test_client: TestClient) -> None:
    list_response = test_client.get("/api/v1/events")
    assert list_response.status_code == 200
    items = list_response.json()
    assert isinstance(items, list)
    assert len(items) >= 1

    first = items[0]
    expected_keys = {
        "id",
        "competitor_id",
        "event_type",
        "title",
        "description",
        "event_date",
        "region",
        "country",
        "traffic_light",
        "threat_score",
        "development_stage",
        "indication",
        "metadata_json",
        "review_status",
        "created_at",
    }
    assert expected_keys.issubset(first.keys())

    detail_response = test_client.get(f"/api/v1/events/{first['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == first["id"]


def test_event_detail_with_bad_id_returns_expected_error(test_client: TestClient) -> None:
    response = test_client.get("/api/v1/events/not-a-uuid")
    assert response.status_code in {404, 422}


def test_create_and_update_event_applies_scoring(
    test_client: TestClient,
) -> None:
    seeded_competitor_id = _get_any_competitor_id(test_client)

    create_payload = {
        "competitor_id": seeded_competitor_id,
        "event_type": "launch",
        "title": f"TEST: launch signal {uuid4()}",
        "description": "Integration test event",
        "event_date": "2026-04-19",
        "region": "North America",
        "country": "United States",
        "development_stage": "Phase 3",
        "indication": "NSCLC",
    }

    created = test_client.post("/api/v1/events", json=create_payload)
    assert created.status_code == 201
    created_body = created.json()

    assert created_body["id"]
    threat_score = created_body.get("threat_score")
    if threat_score is not None:
        assert 0 <= float(threat_score) <= 100
    assert created_body.get("traffic_light") in {"Green", "Amber", "Red"}

    event_id = created_body["id"]
    fetched = test_client.get(f"/api/v1/events/{event_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == event_id

    updated = test_client.patch(
        f"/api/v1/events/{event_id}",
        json={
            "description": "Updated by integration test",
            "development_stage": "Phase 2",
            "country": "Germany",
        },
    )
    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["description"] == "Updated by integration test"
    updated_score = updated_body.get("threat_score")
    if updated_score is not None:
        assert 0 <= float(updated_score) <= 100


def test_create_event_with_missing_required_fields_returns_422(test_client: TestClient) -> None:
    response = test_client.post(
        "/api/v1/events",
        json={"title": "missing competitor and event_type"},
    )
    assert response.status_code == 422
    body = response.json()
    assert "detail" in body


def test_reviews_list_and_create(test_client: TestClient) -> None:
    events = test_client.get("/api/v1/events").json()
    assert isinstance(events, list) and events
    event_id = events[0]["id"]

    list_response = test_client.get("/api/v1/reviews")
    assert list_response.status_code == 200
    reviews = list_response.json()
    assert isinstance(reviews, list)

    create_response = test_client.post(
        "/api/v1/reviews",
        json={
            "event_id": event_id,
            "status": "approved",
            "reviewer": "integration@test.local",
            "review_notes": "Approved by integration suite",
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["event_id"] == event_id
    assert created["status"] == "approved"


def test_dashboards_endpoints_shape_and_ordering(test_client: TestClient) -> None:
    summary = test_client.get("/api/v1/dashboards/summary")
    assert summary.status_code == 200
    summary_body = summary.json()
    for key in ("total_events", "approved", "pending", "rejected", "by_traffic_light"):
        assert key in summary_body

    top = test_client.get("/api/v1/dashboards/top-threats", params={"limit": 10, "approved_only": False})
    assert top.status_code == 200
    top_items = top.json()
    assert isinstance(top_items, list)
    for item in top_items:
        assert {"id", "drug_name", "competitor_name", "threat_score", "traffic_light", "event_date", "country", "indication"}.issubset(item.keys())
        assert item["drug_name"] is not None
    if len(top_items) > 1:
        scores = [item["threat_score"] for item in top_items]
        assert scores == sorted(scores, reverse=True)

    recent = test_client.get("/api/v1/dashboards/recent-events", params={"limit": 10})
    assert recent.status_code == 200
    recent_items = recent.json()
    assert isinstance(recent_items, list)
    for item in recent_items:
        assert "indication" in item
    if len(recent_items) > 1:
        created_values = [datetime.fromisoformat(item["created_at"]) for item in recent_items]
        assert created_values == sorted(created_values, reverse=True)

    queue = test_client.get("/api/v1/dashboards/review-queue", params={"limit": 25})
    assert queue.status_code == 200
    queue_items = queue.json()
    assert isinstance(queue_items, list)
    for item in queue_items:
        assert item["review_status"] == "pending"


def test_dashboards_invalid_limit_returns_422(test_client: TestClient) -> None:
    response = test_client.get("/api/v1/dashboards/top-threats", params={"limit": "bad"})
    assert response.status_code == 422
    assert "detail" in response.json()


def test_intelligence_weekly_digest_v2_shape(test_client: TestClient) -> None:
    response = test_client.get(
        "/api/v1/intelligence/weekly-digest-v2",
        params={"limit": 20, "approved_only": False},
    )
    assert response.status_code == 200

    body = response.json()
    assert set(body.keys()) == {"generated_at", "top_insights", "competitor_summary", "counts"}
    assert set(body["counts"].keys()) == {"red", "amber", "green"}
    assert isinstance(body["top_insights"], list)
    assert isinstance(body["competitor_summary"], list)

    for item in body["top_insights"]:
        assert {
            "id",
            "competitor_id",
            "competitor_name",
            "event_type",
            "title",
            "event_date",
            "created_at",
            "review_status",
            "threat_score",
            "traffic_light",
            "development_stage",
            "indication",
            "country",
            "region",
            "competitor_tier",
            "estimated_launch_year",
            "score_breakdown",
            "summary",
            "risk_reason",
            "recommended_action",
            "confidence_note",
        }.issubset(item.keys())

    if len(body["top_insights"]) > 1:
        scores = [item["threat_score"] for item in body["top_insights"]]
        assert scores == sorted(scores, reverse=True)


def test_clinicaltrials_ingestion_contract_and_idempotent_shape(test_client: TestClient) -> None:
    response_one = test_client.post("/api/v1/jobs/ingest/clinicaltrials")

    if response_one.status_code == 502:
        pytest.skip("ClinicalTrials upstream unavailable from this environment")

    assert response_one.status_code == 200
    body_one = response_one.json()

    expected = {
        "status",
        "created",
        "updated",
        "skipped",
    }
    assert expected.issubset(body_one.keys())
    assert body_one["status"] == "ok"

    response_two = test_client.post("/api/v1/jobs/ingest/clinicaltrials")
    if response_two.status_code == 502:
        pytest.skip("ClinicalTrials upstream unavailable on repeat run")

    assert response_two.status_code == 200
    body_two = response_two.json()
    for counter in ("created", "updated", "skipped"):
        assert isinstance(body_two[counter], int)
        assert body_two[counter] >= 0


def test_n8n_webhook_happy_path_returns_created(test_client: TestClient) -> None:
    payload = {
        "source": "n8n",
        "workflow_id": "daily-intel-v1",
        "event_type": "press_release",
        "payload": {
            "title": f"Webhook event {uuid4()}",
            "competitor_name": "Amgen",
            "drug_name": "Nivolumab (Opdivo)",
            "country": "United States",
            "event_date": "2026-04-19",
            "raw_text": "Amgen shared additional biosimilar development updates.",
        },
    }
    response = test_client.post("/api/v1/webhooks/n8n/event", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["received"] is True
    assert body["event_id"]
    assert 0 <= body["threat_score"] <= 100
    assert body["traffic_light"] in {"Green", "Amber", "Red"}


def test_n8n_webhook_missing_required_fields_returns_422(test_client: TestClient) -> None:
    payload = {
        "source": "n8n",
        "workflow_id": "daily-intel-v1",
        "event_type": "press_release",
        "payload": {
            "title": "Missing drug name payload",
            "competitor_name": "Amgen",
        },
    }
    response = test_client.post("/api/v1/webhooks/n8n/event", json=payload)
    assert response.status_code == 422


def test_n8n_webhook_duplicate_payload_is_idempotent(test_client: TestClient) -> None:
    payload = {
        "source": "n8n",
        "workflow_id": "daily-intel-v1",
        "event_type": "manual",
        "payload": {
            "title": "Idempotent webhook event",
            "competitor_name": "Zydus",
            "drug_name": "Bevacizumab (Avastin)",
            "country": "India",
        },
    }

    first = test_client.post("/api/v1/webhooks/n8n/event", json=payload)
    second = test_client.post("/api/v1/webhooks/n8n/event", json=payload)

    assert first.status_code == 201
    assert second.status_code in {200, 201}
    assert first.json()["event_id"] == second.json()["event_id"]


def test_press_release_ingestion_happy_or_expected_config_error(test_client: TestClient) -> None:
    payload = {
        "source_url": "https://example.com/press/hlx18-phase3",
        "text": (
            "Henlius announced FDA IND clearance for HLX18 and initiation "
            "of a Phase 3 NSCLC program in the United States."
        ),
    }
    response = test_client.post("/api/v1/jobs/ingest/press-release", json=payload)

    if not settings.openrouter_api_key:
        assert response.status_code == 422
        detail = response.json().get("detail")
        detail_text = str(detail)
        assert "OPENROUTER_API_KEY" in detail_text
        return

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "press_release"
    assert "extracted_event" in body
    assert body["event_created"] or body["event_updated"]


def test_press_release_ingestion_invalid_payload_returns_422(test_client: TestClient) -> None:
    response = test_client.post(
        "/api/v1/jobs/ingest/press-release",
        json={"source_url": "https://example.com/press/invalid", "text": "   "},
    )
    assert response.status_code == 422
    assert "detail" in response.json()
