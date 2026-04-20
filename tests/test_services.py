from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import ExternalServiceError
from app.schemas.review import ReviewCreate
from app.services.openrouter_service import OpenRouterService
from app.services import review_service


@pytest.mark.anyio
async def test_openrouter_extract_json_success_with_mocked_http_call() -> None:
    service = OpenRouterService(
        api_key="test-key",
        base_url="https://openrouter.test/api/v1/chat/completions",
        model_primary="model-primary",
        model_fallback="model-fallback",
        timeout_seconds=7,
    )

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"event_type":"approval"}'}}]
    }
    mock_client.post.return_value = mock_response

    with patch("app.services.openrouter_service.httpx.AsyncClient") as async_client_cls:
        async_client_cls.return_value.__aenter__.return_value = mock_client

        payload = await service.extract_json("extract this")

    assert payload == {"event_type": "approval"}
    mock_client.post.assert_awaited_once()


@pytest.mark.anyio
async def test_openrouter_extract_json_raises_external_error_on_http_status() -> None:
    service = OpenRouterService(
        api_key="test-key",
        base_url="https://openrouter.test/api/v1/chat/completions",
        model_primary="model-primary",
        model_fallback="model-fallback",
    )

    request = httpx.Request("POST", "https://openrouter.test/api/v1/chat/completions")
    response = httpx.Response(status_code=502, request=request, text="upstream failure")
    status_error = httpx.HTTPStatusError("bad status", request=request, response=response)

    mock_client = AsyncMock()
    mock_client.post.side_effect = [status_error, status_error]

    with patch("app.services.openrouter_service.httpx.AsyncClient") as async_client_cls:
        async_client_cls.return_value.__aenter__.return_value = mock_client

        with pytest.raises(ExternalServiceError) as exc:
            await service.extract_json("extract this")

    assert "openrouter" in str(exc.value)
    assert mock_client.post.await_count == 2


@pytest.mark.anyio
async def test_openrouter_extract_json_raises_external_error_on_timeout() -> None:
    service = OpenRouterService(
        api_key="test-key",
        base_url="https://openrouter.test/api/v1/chat/completions",
        model_primary="model-primary",
        model_fallback="model-fallback",
    )

    timeout_error = httpx.ReadTimeout("request timed out")

    mock_client = AsyncMock()
    mock_client.post.side_effect = [timeout_error, timeout_error]

    with patch("app.services.openrouter_service.httpx.AsyncClient") as async_client_cls:
        async_client_cls.return_value.__aenter__.return_value = mock_client

        with pytest.raises(ExternalServiceError) as exc:
            await service.extract_json("extract this")

    assert "openrouter" in str(exc.value)
    assert mock_client.post.await_count == 2


@pytest.mark.anyio
async def test_review_service_create_write_path() -> None:
    event_id = uuid.uuid4()
    event = SimpleNamespace(id=event_id, review_status="pending")

    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    async def _refresh(review: object) -> None:
        review.id = uuid.uuid4()  # type: ignore[attr-defined]
        review.created_at = datetime.now(UTC)  # type: ignore[attr-defined]

    session.refresh = AsyncMock(side_effect=_refresh)

    with patch("app.services.review_service._get_event_by_id", new=AsyncMock(return_value=event)):
        result = await review_service.create_review(
            session,
            ReviewCreate(
                event_id=event_id,
                status="APPROVED",
                reviewer="analyst@biosi.ai",
                review_notes="validated",
            ),
        )

    assert result is not None
    assert result.event_id == event_id
    assert result.status == "approved"
    assert event.review_status == "approved"
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_review_service_update_write_path_via_approve_event() -> None:
    event_id = str(uuid.uuid4())
    event = SimpleNamespace(id=uuid.uuid4(), review_status="pending")

    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    async def _refresh(review: object) -> None:
        review.id = uuid.uuid4()  # type: ignore[attr-defined]
        review.created_at = datetime.now(UTC)  # type: ignore[attr-defined]

    session.refresh = AsyncMock(side_effect=_refresh)

    with patch("app.services.review_service._get_event_by_id", new=AsyncMock(return_value=event)):
        result = await review_service.approve_event(
            session,
            event_id,
            reviewer_email="reviewer@biosi.ai",
            comment="approved",
        )

    assert result is not None
    assert result.status == "approved"
    assert result.reviewer == "reviewer@biosi.ai"
    assert event.review_status == "approved"
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_review_service_delete_write_path_via_reject_event() -> None:
    event_id = str(uuid.uuid4())
    event = SimpleNamespace(id=uuid.uuid4(), review_status="pending")

    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()

    async def _refresh(review: object) -> None:
        review.id = uuid.uuid4()  # type: ignore[attr-defined]
        review.created_at = datetime.now(UTC)  # type: ignore[attr-defined]

    session.refresh = AsyncMock(side_effect=_refresh)

    with patch("app.services.review_service._get_event_by_id", new=AsyncMock(return_value=event)):
        result = await review_service.reject_event(
            session,
            event_id,
            reviewer_email="reviewer@biosi.ai",
            comment="rejected",
        )

    assert result is not None
    assert result.status == "rejected"
    assert result.reviewer == "reviewer@biosi.ai"
    assert event.review_status == "rejected"
    session.add.assert_called_once()
    session.commit.assert_awaited_once()
