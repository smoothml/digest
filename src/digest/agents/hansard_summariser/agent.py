from asyncio import Runner
from datetime import date, datetime

from loguru import logger
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel, OpenAIModelSettings

from digest.settings import openai_provider
from digest.site import create_post, format_post, get_all_tags, slugify
from digest.sources.hansard.constants import HansardSourceName, HansardSourceType
from digest.sources.hansard.main import get_hansard_data_source
from digest.agents.hansard_summariser.prompts import (
    EDITOR_SYSTEM_PROMPT_TEMPLATE,
    SUMMARY_SYSTEM_PROMPT,
    TAG_SYSTEM_PROMPT_TEMPLATE,
    TITLE_SYSTEM_PROMPT,
)
from digest.agents.hansard_summariser.schemas import DraftSummary, FinalSummary, Summary


hansard_data_source = get_hansard_data_source()

model = OpenAIModel(
    "gpt-5-2025-08-07",
    provider=openai_provider,
)
model_settings = OpenAIModelSettings(
    openai_reasoning_effort="medium", max_tokens=128000
)
summary_agent = Agent[None, DraftSummary](
    model,
    model_settings=model_settings,
    system_prompt=SUMMARY_SYSTEM_PROMPT,
    output_type=DraftSummary,
)
editor_agent = Agent[str, FinalSummary](
    model,
    model_settings=model_settings,
    deps_type=str,
    output_type=FinalSummary,
)
title_agent = Agent[None, str](
    model, system_prompt=TITLE_SYSTEM_PROMPT, output_type=str
)
tag_agent = Agent[set[str], list[str]](model, deps_type=set[str], output_type=list[str])


@editor_agent.system_prompt
def create_editor_system_prompt(ctx: RunContext[str]) -> str:
    """Create the editor system prompt.

    Args:
        ctx: Run context.

    Returns:
        System prompt.
    """
    return EDITOR_SYSTEM_PROMPT_TEMPLATE.safe_substitute(transcript=ctx.deps).strip()


@tag_agent.system_prompt
def create_tag_system_prompt(ctx: RunContext[set[str]]) -> str:
    """Create the tag generation system prompt.

    Args:
        ctx: Run context.

    Returns:
        System prompt.
    """
    existing_tags = "\n".join([f"- {tag}" for tag in ctx.deps])
    return TAG_SYSTEM_PROMPT_TEMPLATE.safe_substitute(
        existing_tags=existing_tags
    ).strip()


async def get_hansard_summary(
    dt: date, source: HansardSourceType = HansardSourceType.COMMONS
) -> Summary | None:
    """Generate a Hansard summary.

    Args:
        dt: Date to generate summary for.
        source: Source to generate summary from.

    Returns:
        Summary.
    """
    debate = hansard_data_source.get(dt, source)
    debate_str = debate.to_markdown()
    if not debate.exists:
        logger.error(f"No data found for {dt} {source}")
        return None
    logger.info(f"Generating draft summary for {source} on {dt}.")
    draft_summary = await summary_agent.run(debate_str)
    logger.info(f"Generating final summary for {source} on {dt}.")
    final_summary = await editor_agent.run(
        draft_summary.output.to_markdown(), deps=debate_str
    )
    logger.info(f"Quality report:\n{final_summary.output.quality_report}")
    title = await title_agent.run(final_summary.output.to_markdown())
    logger.info(f"Title: {title.output}")
    return Summary(
        title=title.output,
        high_level=final_summary.output.high_level,
        detail=final_summary.output.detail,
        quality_report=final_summary.output.quality_report,
    )


async def get_tags(summary: str, existing_tags: set[str]) -> list[str]:
    """Generate tags for a Hansard summary.

    Args:
        summary: Summary to generate tags for.
        existing_tags: Existing tags to use as dependencies.

    Returns:
        List of tags.
    """
    result = await tag_agent.run(summary, deps=existing_tags)
    tags = [tag.lower() for tag in result.output]
    logger.info(f"Tags: {', '.join(tags)}")
    return tags


def publish_summary(summary: Summary, dt: datetime, source: HansardSourceName) -> None:
    """Publish a Hansard summary.

    Args:
        summary: Summary to publish.
        dt: Date of the summary.
        source: Source of the summary.
    """
    summary_str = summary.to_markdown()
    existing_tags = get_all_tags("hansard")
    with Runner() as runner:
        try:
            tags = runner.run(get_tags(summary_str, existing_tags))
            post_content = format_post(
                content=summary_str,
                dt=dt,
                title=summary.title,
                tags=tags,
            )
            create_post(
                site="hansard",
                content=post_content,
                post_path=f"{dt.date()}-{slugify(summary.title)}.md",
                section=source.value,
            )
        except KeyboardInterrupt:
            logger.info("Publishing cancelled by user")
