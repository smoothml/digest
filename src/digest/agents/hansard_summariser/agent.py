from asyncio import Runner
from datetime import date, datetime

from loguru import logger
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel

from digest.settings import openai_provider
from digest.site import create_post, format_post, get_all_tags
from digest.sources.hansard.constants import HansardSourceType
from digest.sources.hansard.main import get_hansard_data_source
from digest.agents.hansard_summariser.prompts import (
    SUMMARY_SYSTEM_PROMPT,
    TAG_SYSTEM_PROMPT_TEMPLATE,
)
from digest.agents.hansard_summariser.schemas import Summary


hansard_data_source = get_hansard_data_source()

model = OpenAIModel(
    "gpt-5-mini-2025-08-07",
    provider=openai_provider,
)
summary_agent = Agent(model, system_prompt=SUMMARY_SYSTEM_PROMPT, output_type=Summary)
tag_agent = Agent(model, deps_type=set[str], output_type=list[str])


@tag_agent.system_prompt
def create_tag_system_prompt(ctx: RunContext[set[str]]) -> str:
    """Create the tag generation system prompt.

    Args:
        ctx: Run context.

    Returns:
        System prompt.
    """
    existing_tags = "\n".join([f"- {tag}" for tag in ctx.deps])
    return TAG_SYSTEM_PROMPT_TEMPLATE.safe_substitute(existing_tags=existing_tags)


async def get_hansard_summary(
    dt: date, source: HansardSourceType = HansardSourceType.DEBATES
) -> Summary:
    """Generate a Hansard summary.

    Args:
        dt: Date to generate summary for.
        source: Source to generate summary from.

    Returns:
        Summary.
    """
    debate = hansard_data_source.get(dt, source)
    logger.info(f"Generating summary for {source} on {dt}.")
    result = await summary_agent.run(debate.xml_string)
    return result.output


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


def publish_summary(summary: Summary, dt: datetime, source: HansardSourceType) -> None:
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
        except KeyboardInterrupt:
            logger.info("Tag generation cancelled by user")
    post_content = format_post(
        summary_str,
        dt,
        f"{source.value.title()} Summary for {dt.strftime('%B %d, %Y')}",
        tags=tags,
    )
    create_post(
        site="hansard",
        content=post_content,
        post_path=f"{dt.date()}-{source.value}-summary.md",
        section=source.value,
    )
