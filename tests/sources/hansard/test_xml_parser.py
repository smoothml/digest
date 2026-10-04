"""Tests for the Hansard XML parser."""

from __future__ import annotations

import pytest

from digest.sources.hansard.xml_parser import (
    Heading,
    Speech,
    xml_to_blocks,
    xml_to_markdown,
)
from tests import TEST_DATA_DIR


def load_sample_xml() -> str:
    """Load sample XML file.

    Returns:
        str: Sample XML file.
    """
    xml_path = TEST_DATA_DIR / "2025-09-01-debates.xml"
    return xml_path.read_text(encoding="utf-8")


def test_xml_to_blocks_basic_structure() -> None:
    """Test XML to blocks basic structure."""
    xml = load_sample_xml()
    blocks = xml_to_blocks(xml)
    # Should have a mix of headings and speeches
    assert blocks, "No blocks parsed from XML"

    # First block is an oral heading with combined text
    assert isinstance(blocks[0], Heading)
    assert blocks[0].level == "oral"
    assert "Oral Answers to Questions" in blocks[0].text

    # Ensure we parse at least one speech with a speakername
    some_speech = next(b for b in blocks if isinstance(b, Speech) and b.speakername)
    assert some_speech.speakername == "Alison Griffiths"
    # Ensure paragraphs retain pid and text
    assert some_speech.paragraphs, "Speech missing paragraphs"
    first_para = some_speech.paragraphs[0]
    assert first_para.pid == "c1.4/1"
    assert "unemployment" in first_para.text


@pytest.mark.parametrize(
    "marker",
    [
        pytest.param("## Oral Answers to Questions", id="heading"),
        pytest.param("### Work and Pensions", id="subheading"),
        pytest.param("##### Alison Griffiths (Start Question)", id="speech-header"),
        pytest.param(
            "[c1.4/1] What assessment she has made of trends in the level of"
            " unemployment.",
            id="paragraph-pid",
        ),
        pytest.param("*The Secretary of State was asked—*", id="italic-paragraph"),
    ],
)
def test_xml_to_markdown_contains_expected_markers(marker: str) -> None:
    """Rendered Markdown contains headings, speech headers and tagged paragraphs."""
    assert marker in xml_to_markdown(load_sample_xml())
