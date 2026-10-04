"""Tests for digest.publishers.hansard module."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from digest.agents.hansard_summariser.schemas import DetailedSummary, Summary
from digest.publishers.hansard import create_hansard_post
from digest.sources.hansard.constants import HansardSourceName


@pytest.fixture
def sample_summary() -> Summary:
    """Create a sample summary for testing."""
    return Summary(
        title="Test Summary Title",
        high_level="This is a high-level summary.",
        detail=[
            DetailedSummary(
                title="Topic 1",
                summary="This is a detailed summary of topic 1.",
            )
        ],
        quality_report="Quality report content.",
    )


def test_create_hansard_post_formats_post_correctly(
    sample_summary: Summary,
) -> None:
    """Publish function formats post with correct parameters."""
    mock_format_post = MagicMock(return_value="formatted content")
    mock_create_post = MagicMock()

    test_date = date(2025, 1, 15)
    tags = ["tag1", "tag2"]

    with (
        patch("digest.publishers.hansard.format_post", mock_format_post),
        patch("digest.publishers.hansard.create_post", mock_create_post),
    ):
        create_hansard_post(sample_summary, test_date, HansardSourceName.COMMONS, tags)

    mock_format_post.assert_called_once_with(
        content=sample_summary.to_markdown(),
        dt=test_date,
        title=sample_summary.title,
        tags=["tag1", "tag2"],
    )


@pytest.mark.parametrize(
    ("source", "section"),
    [
        pytest.param(HansardSourceName.COMMONS, "commons", id="commons"),
        pytest.param(HansardSourceName.LORDS, "lords", id="lords"),
        pytest.param(
            HansardSourceName.WESTMINSTER_HALL,
            "westminster_hall",
            id="westminster-hall",
        ),
    ],
)
def test_create_hansard_post_creates_post_in_source_section(
    sample_summary: Summary, source: HansardSourceName, section: str
) -> None:
    """Publish function creates the post in the section matching its source."""
    mock_format_post = MagicMock(return_value="formatted content")
    mock_create_post = MagicMock()

    with (
        patch("digest.publishers.hansard.format_post", mock_format_post),
        patch("digest.publishers.hansard.create_post", mock_create_post),
    ):
        create_hansard_post(sample_summary, date(2025, 1, 15), source, ["tag1"])

    mock_create_post.assert_called_once_with(
        site="hansard",
        content="formatted content",
        post_path="2025-01-15-test-summary-title.md",
        section=section,
    )
