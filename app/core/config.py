from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "Biosi"
    service_version: str = "1.0.0"
    app_env: Literal["dev", "staging", "production", "test"] = Field(
        "dev", validation_alias="APP_ENV"
    )
    host: str = Field("0.0.0.0", validation_alias="HOST")
    port: int = Field(8000, validation_alias="PORT")
    secret_key: str = Field(..., validation_alias="SECRET_KEY")

    # CORS — comma-separated list of allowed origins
    cors_origins: list[str] = Field(
        default=[
            "https://app.n8n.cloud",
            "https://fareedkhan.app.n8n.cloud",
            "http://localhost:5678",
            "http://localhost:3000",
        ],
        validation_alias="CORS_ORIGINS",
    )
    cors_allow_all: bool = Field(False, validation_alias="CORS_ALLOW_ALL")

    # Database
    database_url: str = Field(..., validation_alias="DATABASE_URL")
    database_url_direct: str = Field(..., validation_alias="DATABASE_URL_DIRECT")

    # OpenRouter (future milestones)
    openrouter_api_key: str | None = Field(None, validation_alias="OPENROUTER_API_KEY")
    openrouter_model_primary: str = Field(
        "anthropic/claude-3.7-sonnet", validation_alias="OPENROUTER_MODEL_PRIMARY"
    )
    openrouter_model_fallback: str = Field(
        "google/gemini-2.0-flash-001", validation_alias="OPENROUTER_MODEL_FALLBACK"
    )
    openrouter_base_url: str = Field(
        "https://openrouter.ai/api/v1/chat/completions",
        validation_alias="OPENROUTER_BASE_URL",
    )
    openrouter_timeout_seconds: int = Field(45, validation_alias="OPENROUTER_TIMEOUT_SECONDS")

    # External data sources
    clinicaltrials_base_url: str = Field(
        "https://clinicaltrials.gov/api/v2/studies",
        validation_alias="CLINICALTRIALS_BASE_URL",
    )
    clinicaltrials_search_terms: list[str] = Field(
        ["nivolumab biosimilar", "ABP 206", "HLX18"],
        validation_alias="CLINICALTRIALS_SEARCH_TERMS",
    )
    n8n_webhook_base_url: str | None = Field(None, validation_alias="N8N_WEBHOOK_BASE_URL")


settings = Settings()
