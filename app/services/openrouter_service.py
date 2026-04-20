from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import ExternalServiceError, ValidationError


class OpenRouterService:
    """Thin HTTP client for OpenRouter chat-completions."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model_primary: str | None = None,
        model_fallback: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.api_key = api_key or settings.openrouter_api_key
        self.base_url = (base_url or settings.openrouter_base_url).rstrip("/")
        self.model_primary = model_primary or settings.openrouter_model_primary
        self.model_fallback = model_fallback or settings.openrouter_model_fallback
        self.timeout_seconds = timeout_seconds or settings.openrouter_timeout_seconds

        if not self.api_key:
            raise ValidationError("OPENROUTER_API_KEY is required for extraction jobs.")

    async def extract_json(self, prompt: str) -> dict[str, Any]:
        primary_error: ExternalServiceError | None = None

        for model in (self.model_primary, self.model_fallback):
            try:
                return await self._extract_json_for_model(model=model, prompt=prompt)
            except ExternalServiceError as exc:
                if primary_error is None:
                    primary_error = exc

        if primary_error is not None:
            raise primary_error

        raise ExternalServiceError("openrouter", "No model configured.")

    async def _extract_json_for_model(self, model: str, prompt: str) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": "You are an information extraction engine. Return strict JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=float(self.timeout_seconds)) as client:
                response = await client.post(self.base_url, headers=headers, json=payload)
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise ExternalServiceError("openrouter", detail) from exc
        except httpx.HTTPError as exc:
            raise ExternalServiceError("openrouter", str(exc)) from exc

        content = self._message_content(body)
        parsed = self._safe_json_loads(content)
        if not isinstance(parsed, dict):
            raise ExternalServiceError("openrouter", "Model response was not a JSON object.")
        return parsed

    def _message_content(self, body: dict[str, Any]) -> str:
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ExternalServiceError("openrouter", "No choices returned by model.")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ExternalServiceError("openrouter", "Malformed choice payload.")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ExternalServiceError("openrouter", "Missing message payload.")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ExternalServiceError("openrouter", "Empty model content.")
        return content.strip()

    def _safe_json_loads(self, content: str) -> Any:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise ExternalServiceError("openrouter", "Model output was not valid JSON.")
            snippet = content[start : end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError as exc:
                raise ExternalServiceError("openrouter", "Model output was not valid JSON.") from exc
