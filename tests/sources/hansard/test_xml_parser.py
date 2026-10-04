"""Tests for the Hansard XML parser."""

from __future__ import annotations

import pytest

from digest.sources.hansard.xml_parser import (
    Heading,
    Speech,
    xml_to_blocks,
    xml_to_markdown,
)


def test_xml_to_blocks_basic_structure(sample_debate_xml: str) -> None:
    """Blocks open with the oral heading and keep speakers and paragraph IDs."""
    blocks = xml_to_blocks(sample_debate_xml)

    assert isinstance(blocks[0], Heading)
    assert blocks[0].level == "oral"
    assert "Oral Answers to Questions" in blocks[0].text

    speech = next(b for b in blocks if isinstance(b, Speech) and b.speakername)
    assert speech.speakername == "Alison Griffiths"
    assert speech.paragraphs[0].pid == "c1.4/1"
    assert "unemployment" in speech.paragraphs[0].text


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
def test_xml_to_markdown_contains_expected_markers(
    sample_debate_xml: str, marker: str
) -> None:
    """Rendered Markdown contains headings, speech headers and tagged paragraphs."""
    assert marker in xml_to_markdown(sample_debate_xml)
