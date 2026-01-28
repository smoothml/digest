"""Hansard publisher module for creating and publishing summary posts."""

from datetime import date

from digest.agents.hansard_summariser.schemas import Summary
from digest.site import create_post, format_post, slugify
from digest.sources.hansard.constants import HansardSourceName


def create_hansard_post(
    summary: Summary, dt: date, source: HansardSourceName, tags: list[str]
) -> None:
    """Create a Hansard summary post.

    Args:
        summary: Summary to publish.
        dt: Date of the summary.
        source: Source of the summary (commons or lords).
        tags: Tags for the summary post.
    """
    summary_str = summary.to_markdown()
    post_content = format_post(
        content=summary_str,
        dt=dt,
        title=summary.title,
        tags=tags,
    )
    create_post(
        site="hansard",
        content=post_content,
        post_path=f"{dt}-{slugify(summary.title)}.md",
        section=source.value,
    )
