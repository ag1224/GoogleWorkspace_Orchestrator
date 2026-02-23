from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"
    google_scopes: list[str] = [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/userinfo.email",
    ]

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/workspace_orchestrator"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Security
    token_encryption_key: str = ""
    app_secret_key: str = "dev-secret-key"

    # Rate limits
    max_queries_per_hour: int = 100
    google_api_retry_attempts: int = 3
    google_api_retry_base_delay: float = 1.0

    # Sync
    sync_interval_minutes: int = 15
    max_emails_per_sync: int = 200
    max_events_per_sync: int = 200
    max_files_per_sync: int = 200

    # Cache TTLs (seconds)
    embedding_cache_ttl: int = 3600
    intent_cache_ttl: int = 300
    conversation_context_ttl: int = 1800

    demo_mode: bool = False
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
