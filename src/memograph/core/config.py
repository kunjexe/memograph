"""All settings in one place, read from the .env file.

Every setting starts with MEMOGRAPH_ in .env, e.g. MEMOGRAPH_SPECIALIST_MODEL.
Use it anywhere with:  from memograph.core.config import settings
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MEMOGRAPH_", extra="ignore")

    database_url: str = "postgresql+asyncpg://memograph:memograph@localhost:5433/memograph"
    redis_url: str = "redis://localhost:6379/0"
    ollama_url: str = "http://localhost:11434"

    llm_provider: str = "ollama"  # "ollama" now; "anthropic" added later
    specialist_model: str = "qwen3:8b"
    orchestrator_model: str = "qwen3:8b"

    newsapi_key: str = ""
    anthropic_api_key: str = ""
    edgar_user_agent: str = "MemoGraph example@example.com"


settings = Settings()
