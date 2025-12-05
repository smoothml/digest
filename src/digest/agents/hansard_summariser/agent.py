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
    SYNTHESIS_EDITOR_SYSTEM_PROMPT_TEMPLATE,
    SYNTHESIS_SYSTEM_PROMPT,
    TAG_SYSTEM_PROMPT_TEMPLATE,
    TITLE_SYSTEM_PROMPT,
    TOPIC_EDITOR_SYSTEM_PROMPT_TEMPLATE,
    TOPIC_SUMMARY_SYSTEM_PROMPT,
)
from digest.agents.hansard_summariser.schemas import (
    CombinedSummary,
    DetailedSummary,
    DraftSummary,
    EditedCombinedSummary,
    EditedTopicSummary,
    FinalSummary,
    Summary,
    TopicSummary,
)
from digest.sources.hansard.xml_parser import Topic, xml_to_topics


hansard_data_source = get_hansard_data_source()

model = OpenAIModel(
    "gpt-5-2025-08-07",
    provider=openai_provider,
)
model_settings = OpenAIModelSettings(
    openai_reasoning_effort="medium", max_tokens=128000
)
summary_agent = Agent(
    model,
    model_settings=model_settings,
    system_prompt=SUMMARY_SYSTEM_PROMPT,
    output_type=DraftSummary,
)
editor_agent = Agent(
    model,
    model_settings=model_settings,
    deps_type=str,
    output_type=FinalSummary,
)
title_agent = Agent(model, system_prompt=TITLE_SYSTEM_PROMPT, output_type=str)
tag_agent = Agent(model, deps_type=set[str], output_type=list[str])
topic_agent = Agent(
    model,
    model_settings=model_settings,
    system_prompt=TOPIC_SUMMARY_SYSTEM_PROMPT,
    output_type=TopicSummary,
)
synthesis_agent = Agent(
    model,
    model_settings=model_settings,
    system_prompt=SYNTHESIS_SYSTEM_PROMPT,
    output_type=CombinedSummary,
)
topic_editor_agent = Agent(
    model,
    model_settings=model_settings,
    deps_type=str,
    output_type=EditedTopicSummary,
)
synthesis_editor_agent = Agent(
    model,
    model_settings=model_settings,
    deps_type=str,
    output_type=EditedCombinedSummary,
)


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


@topic_editor_agent.system_prompt
def create_topic_editor_system_prompt(ctx: RunContext[str]) -> str:
    """Create the topic editor system prompt.

    Args:
        ctx: Run context.

    Returns:
        System prompt.
    """
    return TOPIC_EDITOR_SYSTEM_PROMPT_TEMPLATE.safe_substitute(
        transcript=ctx.deps
    ).strip()


@synthesis_editor_agent.system_prompt
def create_synthesis_editor_system_prompt(ctx: RunContext[str]) -> str:
    """Create the synthesis editor system prompt.

    Args:
        ctx: Run context.

    Returns:
        System prompt.
    """
    return SYNTHESIS_EDITOR_SYSTEM_PROMPT_TEMPLATE.safe_substitute(
        summaries=ctx.deps
    ).strip()


async def summarise_topic(topic: Topic) -> EditedTopicSummary:
    """Summarise a single topic with editor verification.

    Args:
        topic: Topic to summarise.

    Returns:
        EditedTopicSummary with title, summary, and quality_report.
    """
    transcript = topic.to_markdown()

    draft = await topic_agent.run(transcript)

    draft_text = f"Title: {draft.output.title}\n\nSummary: {draft.output.summary}"
    edited = await topic_editor_agent.run(draft_text, deps=transcript)

    return edited.output


async def synthesise_summaries(
    topic_summaries: list[EditedTopicSummary], dt: date, source: HansardSourceType
) -> EditedCombinedSummary:
    """Combine topic summaries with editor verification.

    Args:
        topic_summaries: List of edited topic summaries.
        dt: Date of the debate.
        source: Source of the debate.

    Returns:
        EditedCombinedSummary with title, high_level, and quality_report.
    """
    summaries_text = f"Date: {dt.isoformat()}\nChamber: {source.value}\n\n"
    for i, ts in enumerate(topic_summaries, 1):
        summaries_text += f"## Topic {i}: {ts.title}\n\n{ts.summary}\n\n"

    draft = await synthesis_agent.run(summaries_text)

    draft_text = f"Title: {draft.output.title}\n\nHigh-Level: {draft.output.high_level}"
    edited = await synthesis_editor_agent.run(draft_text, deps=summaries_text)

    return edited.output


async def get_hansard_summary(
    dt: date, source: HansardSourceType = HansardSourceType.COMMONS
) -> Summary | None:
    """Generate a Hansard summary by processing topics individually with editor verification.

    Args:
        dt: Date to generate summary for.
        source: Source to generate summary from.

    Returns:
        Summary with combined high-level and detailed sections, plus concatenated quality reports.
    """
    debate = hansard_data_source.get(dt, source)
    if not debate.exists:
        logger.error(f"No debate found for {dt} {source}")
        return None

    topics = xml_to_topics(debate.xml_string)
    logger.info(f"Found {len(topics)} topics for {source} on {dt}")

    edited_topic_summaries: list[EditedTopicSummary] = []
    for i, topic in enumerate(topics):
        logger.info(f"Summarising topic {i + 1}/{len(topics)}: {topic.title}")
        edited = await summarise_topic(topic)
        logger.info(f"Topic quality report:\n{edited.quality_report}")
        edited_topic_summaries.append(edited)

    logger.info("Synthesising combined summary")
    edited_combined = await synthesise_summaries(edited_topic_summaries, dt, source)
    logger.info(f"Synthesis quality report:\n{edited_combined.quality_report}")

    quality_reports = []
    for ts in edited_topic_summaries:
        quality_reports.append(f"### {ts.title}\n{ts.quality_report}")
    quality_reports.append(f"### Combined Summary\n{edited_combined.quality_report}")
    combined_quality_report = "\n\n".join(quality_reports)

    logger.info(f"Title: {edited_combined.title.title()}")
    return Summary(
        title=edited_combined.title.title(),
        high_level=edited_combined.high_level,
        detail=[
            DetailedSummary(title=ts.title, summary=ts.summary)
            for ts in edited_topic_summaries
        ],
        quality_report=combined_quality_report,
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
        except KeyboardInterrupt:
            logger.info("Tag generation cancelled by user")
            tags = []
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
