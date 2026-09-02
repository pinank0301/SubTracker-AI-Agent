from functools import lru_cache
from typing import List, Union
# pyrefly: ignore [missing-import]
from pydantic import Field, field_validator
# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings loaded from environment variables and .env file.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    # PostgreSQL Database
    DATABASE_URL: str = "postgresql://postgres:root@localhost:5432/subtracker"

    # General App Settings
    APP_NAME: str = "Subscription AI Agent Service"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    APP_HOST: str = "0.0.0.0"
    DEBUG: bool = True

    # CORS Settings
    CORS_ORIGINS: Union[List[str], str] = ["*"]

    # Cloudflare Workers AI (OpenAI-Compatible Endpoint)
    # Base URL format: https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/v1
    OPENAI_API_BASE: str = Field(
        default="",
        description="Base URL for Cloudflare Workers AI OpenAI-compatible endpoint"
    )
    OPENAI_API_KEY: str = Field(
        default="",
        description="Cloudflare API Token for Workers AI"
    )
    OPENAI_MODEL_NAME: str = Field(
        default="@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        description="Cloudflare Workers AI model identifier (e.g. @cf/meta/llama-3.3-70b-instruct-fp8-fast)"
    )
    OPENAI_TEMPERATURE: float = 0.2
    OPENAI_MAX_TOKENS: int = 2048
    OPENAI_REQUEST_TIMEOUT: float = 30.0

    # Spring Boot Subscription Microservice URL
    SUBSCRIPTION_SERVICE_BASE_URL: str = "http://localhost:8082"
    SUBSCRIPTION_SERVICE_TIMEOUT_SECONDS: float = 5.0
    USE_MOCK_FALLBACK_IF_SERVICE_OFFLINE: bool = True

    # LangChain Guardrails
    GUARDRAIL_STRICT_DOMAIN_MODE: bool = True
    GUARDRAIL_REJECTION_THRESHOLD: float = 0.75

    # Real-Time Live Web Search
    ENABLE_LIVE_WEB_SEARCH: bool = True
    WEB_SEARCH_MAX_RESULTS: int = 3
    WEB_SEARCH_TIMEOUT_SECONDS: float = 5.0

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        elif isinstance(v, str) and v.startswith("["):
            import json
            try:
                return json.loads(v)
            except Exception:
                return ["*"]
        return ["*"]

    @property
    def normalized_openai_base_url(self) -> str:
        """
        Normalizes base URL to ensure proper endpoint formatting for OpenAI client.
        """
        base = self.OPENAI_API_BASE.rstrip("/")
        # If it doesn't already end in /v1, OpenAI client might append it, but we provide clean base
        return base


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
