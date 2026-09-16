"""Settings for the Hansard summariser agent."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from digest.agents.hansard_summariser.constants import ReasoningEffort
from digest.constants import ROOT_DIR


class HansardSummariserAgentSettings(BaseSettings):
    """Settings for the Hansard summariser agent.

    Attributes:
        model: OpenAI model used by every summariser agent.
        summary_reasoning_effort: Reasoning effort for the draft summary agent.
        editor_reasoning_effort: Reasoning effort for the editor agent.
        title_reasoning_effort: Reasoning effort for the title agent.
        tag_reasoning_effort: Reasoning effort for the tag agent.
        max_tokens: Maximum number of tokens a summariser agent may generate.
    """

    model_config = SettingsConfigDict(
        env_prefix="HANSARD_SUMMARISER_",
        env_file=ROOT_DIR / ".env",
        extra="ignore",
    )

    model: str = Field(default="gpt-5.6-luna", min_length=1)
    summary_reasoning_effort: ReasoningEffort = "medium"
    editor_reasoning_effort: ReasoningEffort = "high"
    title_reasoning_effort: ReasoningEffort = "low"
    tag_reasoning_effort: ReasoningEffort = "low"
    max_tokens: int = Field(default=128000, gt=0)


@lru_cache
def get_hansard_summariser_agent_settings() -> HansardSummariserAgentSettings:
    """Get the agent settings, reading the environment on first call.

    Returns:
        The Hansard summariser agent settings.
    """
    return HansardSummariserAgentSettings()
