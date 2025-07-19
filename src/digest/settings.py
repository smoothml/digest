from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_settings import BaseSettings


class ApplicationSettings(BaseSettings):
    """Application settings."""

    openai_api_key: str
    openai_base_url: str | None = None


application_settings = ApplicationSettings()
openai_provider = OpenAIProvider(
    api_key=application_settings.openai_api_key,
    base_url=application_settings.openai_base_url,
)
