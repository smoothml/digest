"""Hansard summariser agent module.

This module provides agent factory functions and helper functions for
generating Hansard summaries. Agents are stateless AI components that
perform specific summarization tasks.
"""

from loguru import logger
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings

from digest.agents.hansard_summariser.constants import ReasoningEffort
from digest.agents.hansard_summariser.prompts import (
    EDITOR_SYSTEM_PROMPT_TEMPLATE,
    SUMMARY_SYSTEM_PROMPT,
    TAG_SYSTEM_PROMPT_TEMPLATE,
    TITLE_SYSTEM_PROMPT,
)
from digest.agents.hansard_summariser.schemas import DraftSummary, FinalSummary
from digest.agents.hansard_summariser.settings import hansard_summariser_agent_settings
from digest.settings import get_openai_provider


def _get_default_model() -> OpenAIResponsesModel:
    """Get the default OpenAI model.

    Returns:
        The default OpenAI model instance.
    """
    return OpenAIResponsesModel(
        hansard_summariser_agent_settings.model, provider=get_openai_provider()
    )


def _get_model_settings(effort: ReasoningEffort) -> OpenAIResponsesModelSettings:
    """Get model settings for a given reasoning effort.

    Args:
        effort: Reasoning effort the agent should use.

    Returns:
        Model settings carrying the given reasoning effort.
    """
    return OpenAIResponsesModelSettings(
        openai_reasoning_effort=effort,
        max_tokens=hansard_summariser_agent_settings.max_tokens,
    )


def create_summary_agent(
    model: OpenAIResponsesModel | None = None,
) -> Agent[None, DraftSummary]:
    """Create a summary agent for generating draft summaries.

    Args:
        model: Optional model to use. If not provided, uses the default model.

    Returns:
        An agent configured for draft summary generation.
    """
    return Agent[None, DraftSummary](
        model or _get_default_model(),
        model_settings=_get_model_settings(
            hansard_summariser_agent_settings.summary_reasoning_effort
        ),
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        output_type=DraftSummary,
    )


def create_editor_agent(
    model: OpenAIResponsesModel | None = None,
) -> Agent[str, FinalSummary]:
    """Create an editor agent for refining draft summaries.

    Args:
        model: Optional model to use. If not provided, uses the default model.

    Returns:
        An agent configured for summary editing.
    """
    agent = Agent[str, FinalSummary](
        model or _get_default_model(),
        model_settings=_get_model_settings(
            hansard_summariser_agent_settings.editor_reasoning_effort
        ),
        deps_type=str,
        output_type=FinalSummary,
    )

    @agent.system_prompt
    def editor_system_prompt(ctx: RunContext[str]) -> str:
        return EDITOR_SYSTEM_PROMPT_TEMPLATE.safe_substitute(
            transcript=ctx.deps
        ).strip()

    return agent


def create_title_agent(model: OpenAIResponsesModel | None = None) -> Agent[None, str]:
    """Create a title agent for generating summary titles.

    Args:
        model: Optional model to use. If not provided, uses the default model.

    Returns:
        An agent configured for title generation.
    """
    return Agent[None, str](
        model or _get_default_model(),
        model_settings=_get_model_settings(
            hansard_summariser_agent_settings.title_reasoning_effort
        ),
        system_prompt=TITLE_SYSTEM_PROMPT,
        output_type=str,
    )


def create_tag_agent(
    model: OpenAIResponsesModel | None = None,
) -> Agent[set[str], list[str]]:
    """Create a tag agent for generating summary tags.

    Args:
        model: Optional model to use. If not provided, uses the default model.

    Returns:
        An agent configured for tag generation.
    """
    agent = Agent[set[str], list[str]](
        model or _get_default_model(),
        model_settings=_get_model_settings(
            hansard_summariser_agent_settings.tag_reasoning_effort
        ),
        deps_type=set[str],
        output_type=list[str],
    )

    @agent.system_prompt
    def tag_system_prompt(ctx: RunContext[set[str]]) -> str:
        existing_tags = "\n".join([f"- {tag}" for tag in ctx.deps])
        return TAG_SYSTEM_PROMPT_TEMPLATE.safe_substitute(
            existing_tags=existing_tags
        ).strip()

    return agent


async def generate_draft_summary(debate: str) -> DraftSummary:
    """Generate draft debate summary.

    Args:
        debate: Debate in markdown format.

    Returns:
        The draft summary.
    """
    draft_summary = await create_summary_agent().run(debate)
    return draft_summary.output


async def generate_final_summary(draft_summary: str, debate: str) -> FinalSummary:
    """Generate final debate summary.

    Args:
        draft_summary: Draft summary in markdown format.
        debate: The full debate in markdown format.

    Returns:
        The final summary object.
    """
    final_summary = await create_editor_agent().run(draft_summary, deps=debate)
    return final_summary.output


async def generate_title(summary: str) -> str:
    """Generate summary post title.

    Args:
        summary: The final debate summary in markdown format.

    Returns:
        The title string.
    """
    title = await create_title_agent().run(summary)
    return title.output


async def generate_tags(summary: str, existing_tags: set[str]) -> list[str]:
    """Generate tags for a Hansard summary.

    Args:
        summary: Summary to generate tags for.
        existing_tags: Existing tags to use as dependencies.

    Returns:
        List of tags.
    """
    result = await create_tag_agent().run(summary, deps=existing_tags)
    tags = [tag.lower() for tag in result.output]
    logger.info(f"Tags: {', '.join(tags)}")
    return tags
