"""Tests for digest.services.hansard module."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from digest.agents.hansard_summariser.schemas import (
    DetailedSummary,
    DraftSummary,
    FinalSummary,
    Summary,
)
from digest.services.hansard import create_hansard_summary, publish_hansard_summary
from digest.sources.hansard.constants import HansardSourceName


def _make_mock_debate(*, exists: bool) -> MagicMock:
    debate = MagicMock()
    debate.exists = exists
    debate.to_markdown.return_value = "# Debate content" if exists else ""
    return debate


def _make_draft_summary() -> DraftSummary:
    return DraftSummary(
        high_level="High level summary",
        detail=[DetailedSummary(title="Topic", summary="Details")],
    )


def _make_final_summary() -> FinalSummary:
    return FinalSummary(
        high_level="Edited high level summary",
        detail=[DetailedSummary(title="Topic", summary="Edited details")],
        quality_report="Quality report",
    )


def _make_summary() -> Summary:
    return Summary(
        title="Test",
        high_level="High level",
        detail=[DetailedSummary(title="Topic", summary="Details")],
        quality_report="Report",
    )


async def test_create_hansard_summary_returns_none_when_no_data() -> None:
    """Service returns None when no debate data is found."""
    mock_data_source = MagicMock()
    mock_data_source.get.return_value = _make_mock_debate(exists=False)

    result = await create_hansard_summary(
        date(2025, 1, 15), HansardSourceName.COMMONS, mock_data_source
    )

    assert result is None


async def test_create_hansard_summary_orchestrates_workflow() -> None:
    """Service orchestrates the summary generation workflow correctly."""
    mock_data_source = MagicMock()
    mock_data_source.get.return_value = _make_mock_debate(exists=True)

    draft = _make_draft_summary()
    final = _make_final_summary()
    mock_generate_draft = AsyncMock(return_value=draft)
    mock_generate_final = AsyncMock(return_value=final)
    mock_generate_title = AsyncMock(return_value="Test Title")

    with (
        patch("digest.services.hansard.generate_draft_summary", mock_generate_draft),
        patch("digest.services.hansard.generate_final_summary", mock_generate_final),
        patch("digest.services.hansard.generate_title", mock_generate_title),
    ):
        result = await create_hansard_summary(
            date(2025, 1, 15), HansardSourceName.COMMONS, mock_data_source
        )

    mock_generate_draft.assert_called_once_with("# Debate content")
    mock_generate_final.assert_called_once_with(draft.to_markdown(), "# Debate content")
    mock_generate_title.assert_called_once_with(final.to_markdown())

    assert result is not None
    assert isinstance(result, Summary)
    assert result.title == "Test Title"
    assert result.high_level == final.high_level
    assert result.detail == final.detail
    assert result.quality_report == final.quality_report


async def test_publish_hansard_summary_calls_get_all_tags() -> None:
    """Service retrieves existing tags from the hansard site."""
    summary = _make_summary()
    mock_get_all_tags = MagicMock(return_value={"economy", "healthcare"})
    mock_generate_tags = AsyncMock(return_value=["economy", "defence"])
    mock_create_post = MagicMock()

    with (
        patch("digest.services.hansard.get_all_tags", mock_get_all_tags),
        patch("digest.services.hansard.generate_tags", mock_generate_tags),
        patch("digest.services.hansard.create_hansard_post", mock_create_post),
    ):
        await publish_hansard_summary(
            summary, date(2025, 1, 15), HansardSourceName.COMMONS
        )

    mock_get_all_tags.assert_called_once_with("hansard")


async def test_publish_hansard_summary_calls_generate_tags() -> None:
    """Service generates tags using the summary markdown and existing tags."""
    summary = _make_summary()
    existing_tags = {"economy", "healthcare"}
    mock_get_all_tags = MagicMock(return_value=existing_tags)
    mock_generate_tags = AsyncMock(return_value=["economy", "defence"])
    mock_create_post = MagicMock()

    with (
        patch("digest.services.hansard.get_all_tags", mock_get_all_tags),
        patch("digest.services.hansard.generate_tags", mock_generate_tags),
        patch("digest.services.hansard.create_hansard_post", mock_create_post),
    ):
        await publish_hansard_summary(
            summary, date(2025, 1, 15), HansardSourceName.COMMONS
        )

    mock_generate_tags.assert_called_once_with(summary.to_markdown(), existing_tags)


async def test_publish_hansard_summary_calls_create_hansard_post() -> None:
    """Service creates the post with the summary, date, source, and generated tags."""
    summary = _make_summary()
    generated_tags = ["economy", "defence"]
    mock_get_all_tags = MagicMock(return_value={"economy", "healthcare"})
    mock_generate_tags = AsyncMock(return_value=generated_tags)
    mock_create_post = MagicMock()

    with (
        patch("digest.services.hansard.get_all_tags", mock_get_all_tags),
        patch("digest.services.hansard.generate_tags", mock_generate_tags),
        patch("digest.services.hansard.create_hansard_post", mock_create_post),
    ):
        await publish_hansard_summary(
            summary, date(2025, 1, 15), HansardSourceName.COMMONS
        )

    mock_create_post.assert_called_once_with(
        summary, date(2025, 1, 15), HansardSourceName.COMMONS, generated_tags
    )


async def test_create_hansard_summary_raises_for_unsupported_source() -> None:
    """Service raises ValueError when source is not in SOURCE_NAME_TO_TYPE_MAP."""
    mock_data_source = MagicMock()

    with patch(
        "digest.services.hansard.SOURCE_NAME_TO_TYPE_MAP",
        {},
    ):
        with pytest.raises(ValueError, match="Unsupported Hansard source"):
            await create_hansard_summary(
                date(2025, 1, 15), HansardSourceName.COMMONS, mock_data_source
            )
