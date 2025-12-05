from __future__ import annotations

from datetime import date

from digest.sources.hansard.xml_parser import (
    xml_to_blocks,
    xml_to_markdown,
    xml_to_topics,
)
from digest.sources.hansard.main import Debate
from digest.sources.hansard.constants import HansardSourceType
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
    from digest.sources.hansard.xml_parser import Heading, Speech

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


def test_xml_to_markdown_contains_expected_markers() -> None:
    """Test XML to Markdown contains expected markers."""
    xml = load_sample_xml()
    md = xml_to_markdown(xml)

    # Headings rendered
    assert "## Oral Answers to Questions" in md
    assert "### Work and Pensions" in md

    # Speech header contains speaker name and type
    assert "##### Alison Griffiths (Start Question)" in md

    # Paragraph line includes [pid] prefix
    assert (
        "[c1.4/1] What assessment she has made of trends in the level of unemployment."
        in md
    )

    # Italic paragraphs are wrapped with *...*
    assert "*The Secretary of State was asked—*" in md


def test_debate_to_markdown_roundtrip() -> None:
    """Test Debate to Markdown roundtrip."""
    xml = load_sample_xml()
    d = Debate(
        date=date(2025, 9, 1),
        source=HansardSourceType.COMMONS,
        xml_string=xml,
        exists=True,
    )
    md = d.to_markdown()
    # Spot-check a couple of expectations from above
    assert "### Work and Pensions" in md
    assert "[c1.5/1] The unemployment rate is 4.7%" in md


def test_xml_to_topics_splits_by_major_heading() -> None:
    """Test that topics are split by major-heading."""
    xml = load_sample_xml()
    topics = xml_to_topics(xml)

    assert len(topics) >= 2, "Should have at least 2 topics"

    first_topic = topics[0]
    assert (
        "Work and Pensions" in first_topic.title or "Oral Answers" in first_topic.title
    )
    assert first_topic.blocks, f"Topic '{first_topic.title}' has no blocks"


def test_xml_to_topics_preserves_minor_headings_within_topic() -> None:
    """Test that minor-headings are included within topics."""
    xml = load_sample_xml()
    topics = xml_to_topics(xml)

    wp_topic = next(
        (
            t
            for t in topics
            if "Work and Pensions" in t.title or "Oral Answers" in t.title
        ),
        None,
    )
    assert wp_topic is not None, "Work and Pensions topic not found"

    from digest.sources.hansard.xml_parser import Heading

    minor_headings = [
        b for b in wp_topic.blocks if isinstance(b, Heading) and b.level == "minor"
    ]
    assert minor_headings, "Should have minor headings within topic"


def test_topic_to_markdown_produces_valid_output() -> None:
    """Test that topic.to_markdown() produces valid markdown."""
    xml = load_sample_xml()
    topics = xml_to_topics(xml)

    for topic in topics:
        md = topic.to_markdown()
        assert md, f"Topic '{topic.title}' produced empty markdown"
        assert "#" in md, "Markdown should contain headings"


def test_empty_topics_are_filtered() -> None:
    """Test that topics with fewer than 2 speeches are filtered out."""
    xml = load_sample_xml()
    topics = xml_to_topics(xml)

    from digest.sources.hansard.xml_parser import Speech

    for topic in topics:
        speech_count = sum(1 for b in topic.blocks if isinstance(b, Speech))
        assert speech_count >= 2, (
            f"Topic '{topic.title}' should have at least 2 speeches"
        )
