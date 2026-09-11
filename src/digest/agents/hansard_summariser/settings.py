"""Settings for the Hansard summariser agent."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from digest.agents.hansard_summariser.constants import ReasoningEffort


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

    model_config = SettingsConfigDict(env_prefix="HANSARD_SUMMARISER_")

    model: str = Field(default="gpt-5.6-luna", min_length=1)
    summary_reasoning_effort: ReasoningEffort = "medium"
    editor_reasoning_effort: ReasoningEffort = "high"
    title_reasoning_effort: ReasoningEffort = "low"
    tag_reasoning_effort: ReasoningEffort = "low"
    max_tokens: int = Field(default=128000, gt=0)


hansard_summariser_agent_settings = HansardSummariserAgentSettings()
