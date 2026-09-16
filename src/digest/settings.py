from functools import lru_cache

from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_settings import BaseSettings, SettingsConfigDict

from digest.constants import ROOT_DIR


class ApplicationSettings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        extra="ignore",
    )

    openai_api_key: str
    openai_base_url: str | None = None

    data_cache_url: str = f"file://{ROOT_DIR}/data"


@lru_cache
def get_application_settings() -> ApplicationSettings:
    """Get the application settings, reading the environment on first call.

    Returns:
        The application settings.
    """
    return ApplicationSettings()


@lru_cache
def get_openai_provider() -> OpenAIProvider:
    """Get the OpenAI provider, building it on first call.

    Returns:
        The OpenAI provider configured from the application settings.
    """
    settings = get_application_settings()
    return OpenAIProvider(
        api_key=settings.openai_api_key, base_url=settings.openai_base_url
    )
