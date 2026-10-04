"""Tests for digest.services.hansard module."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import pytest

from digest.agents.hansard_summariser.schemas import (
    DetailedSummary,
    DraftSummary,
    FinalSummary,
    Summary,
)
from digest.services.hansard import create_hansard_summary, publish_hansard_summary
from digest.sources.hansard.constants import HansardSourceName, HansardSourceType
from digest.sources.hansard.main import Debate, HansardDataSource

_TEST_DATE = date(2025, 1, 15)


def _make_data_source(
    *, xml_string: str = "", exists: bool = False, fetch_failed: bool = False
) -> MagicMock:
    data_source: MagicMock = create_autospec(HansardDataSource, instance=True)
    data_source.get.return_value = Debate(
        date=_TEST_DATE,
        source=HansardSourceType.COMMONS,
        xml_string=xml_string,
        exists=exists,
        fetch_failed=fetch_failed,
    )
    return data_source


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


@pytest.mark.parametrize(
    ("fetch_failed", "message"),
    [
        pytest.param(False, "No data found", id="absent"),
        pytest.param(True, "outage", id="fetch-failed"),
    ],
)
async def test_create_hansard_summary_returns_none_without_debate(
    caplog: pytest.LogCaptureFixture, fetch_failed: bool, message: str
) -> None:
    """Service returns None and logs whether the debate is absent or unreachable."""
    data_source = _make_data_source(fetch_failed=fetch_failed)

    result = await create_hansard_summary(
        _TEST_DATE, HansardSourceName.COMMONS, data_source
    )

    assert result is None
    assert [record.levelname for record in caplog.records] == ["ERROR"]
    assert message in caplog.text


async def test_create_hansard_summary_orchestrates_workflow(
    sample_debate_xml: str,
) -> None:
    """Service fetches the debate, drafts, edits and titles the summary."""
    data_source = _make_data_source(xml_string=sample_debate_xml, exists=True)
    debate_markdown = data_source.get.return_value.to_markdown()

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
            _TEST_DATE, HansardSourceName.COMMONS, data_source
        )

    data_source.get.assert_called_once_with(_TEST_DATE, HansardSourceType.COMMONS)
    mock_generate_draft.assert_called_once_with(debate_markdown)
    mock_generate_final.assert_called_once_with(draft.to_markdown(), debate_markdown)
    mock_generate_title.assert_called_once_with(final.to_markdown())

    assert result is not None
    assert result.title == "Test Title"
    assert result.high_level == final.high_level
    assert result.detail == final.detail
    assert result.quality_report == final.quality_report


async def test_publish_hansard_summary_orchestrates_workflow() -> None:
    """Service tags the summary against existing site tags, then creates the post."""
    summary = _make_summary()
    existing_tags = {"economy", "healthcare"}
    generated_tags = ["economy", "defence"]
    mock_get_all_tags = MagicMock(return_value=existing_tags)
    mock_generate_tags = AsyncMock(return_value=generated_tags)
    mock_create_post = MagicMock()

    with (
        patch("digest.services.hansard.get_all_tags", mock_get_all_tags),
        patch("digest.services.hansard.generate_tags", mock_generate_tags),
        patch("digest.services.hansard.create_hansard_post", mock_create_post),
    ):
        await publish_hansard_summary(summary, _TEST_DATE, HansardSourceName.COMMONS)

    mock_get_all_tags.assert_called_once_with("hansard")
    mock_generate_tags.assert_called_once_with(summary.to_markdown(), existing_tags)
    mock_create_post.assert_called_once_with(
        summary, _TEST_DATE, HansardSourceName.COMMONS, generated_tags
    )


async def test_create_hansard_summary_raises_for_unsupported_source() -> None:
    """Service raises ValueError when source is not in SOURCE_NAME_TO_TYPE_MAP."""
    data_source = _make_data_source()

    with (
        patch("digest.services.hansard.SOURCE_NAME_TO_TYPE_MAP", {}),
        pytest.raises(ValueError, match="Unsupported Hansard source"),
    ):
        await create_hansard_summary(_TEST_DATE, HansardSourceName.COMMONS, data_source)

    data_source.get.assert_not_called()
