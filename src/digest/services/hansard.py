"""Hansard service module for orchestrating summary generation workflows."""

from datetime import date

from loguru import logger

from digest.agents.hansard_summariser.agent import (
    generate_draft_summary,
    generate_final_summary,
    generate_tags,
    generate_title,
)
from digest.agents.hansard_summariser.schemas import Summary
from digest.publishers.hansard import create_hansard_post
from digest.site import get_all_tags
from digest.sources.hansard.constants import SOURCE_NAME_TO_TYPE_MAP, HansardSourceName
from digest.sources.hansard.main import HansardDataSource


async def create_hansard_summary(
    dt: date,
    source: HansardSourceName,
    data_source: HansardDataSource,
) -> Summary | None:
    """Create a Hansard summary.

    Args:
        dt: Date to generate summary for.
        source: Source to generate summary from.
        data_source: Hansard data source to retrieve debates from.

    Returns:
        The generated Summary object, or None if no data found.
    """
    if source not in SOURCE_NAME_TO_TYPE_MAP:
        raise ValueError(
            f"Unsupported Hansard source: {source!r}. "
            f"Supported sources: {', '.join(str(s) for s in SOURCE_NAME_TO_TYPE_MAP)}"
        )
    source_type = SOURCE_NAME_TO_TYPE_MAP[source]

    debate = data_source.get(dt, source_type)
    if not debate.exists:
        if debate.fetch_failed:
            logger.error(
                f"Failed to fetch {source} for {dt} (possible outage); skipping"
            )
        else:
            logger.error(f"No data found for {dt} {source}")
        return None

    debate_str = debate.to_markdown()

    logger.info(f"Generating draft summary for {source} on {dt}.")
    draft_summary = await generate_draft_summary(debate_str)

    logger.info(f"Generating final summary for {source} on {dt}.")
    final_summary = await generate_final_summary(
        draft_summary.to_markdown(), debate_str
    )

    logger.info(f"Quality report:\n{final_summary.quality_report}")

    title = await generate_title(final_summary.to_markdown())
    logger.info(f"Title: {title}")

    return Summary(
        title=title,
        high_level=final_summary.high_level,
        detail=final_summary.detail,
        quality_report=final_summary.quality_report,
    )


async def publish_hansard_summary(
    summary: Summary, dt: date, source: HansardSourceName
) -> None:
    """Generate tags and publish a Hansard summary as a post.

    Orchestrates tag retrieval, tag generation, and post creation.

    Args:
        summary: Summary to publish.
        dt: Date of the summary.
        source: Source of the summary (commons or lords).
    """
    existing_tags = get_all_tags("hansard")
    tags = await generate_tags(summary.to_markdown(), existing_tags)
    create_hansard_post(summary, dt, source, tags)
