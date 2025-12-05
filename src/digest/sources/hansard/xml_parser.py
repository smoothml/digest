from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Optional
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class Paragraph:
    pid: str
    text: str
    italic: bool = False
    qnum: Optional[str] = None


@dataclass(frozen=True)
class Speech:
    id: str
    speakername: Optional[str]
    type: Optional[str]
    paragraphs: list[Paragraph]


@dataclass(frozen=True)
class Heading:
    id: str
    level: Literal["oral", "major", "minor"]
    text: str


Block = Speech | Heading


@dataclass(frozen=True)
class Topic:
    """A single major topic from the debate transcript."""

    id: str
    title: str
    blocks: list[Block]

    def to_markdown(self) -> str:
        """Convert topic blocks to markdown."""
        return blocks_to_markdown(self.blocks)


def _normalize_ws(s: str) -> str:
    return " ".join(s.split())


def _element_text(el: ET.Element) -> str:
    # Join inner text recursively, then normalize whitespace
    return _normalize_ws("".join(el.itertext()))


def _parse_heading(el: ET.Element) -> Heading:
    tag = el.tag
    if tag not in {"oral-heading", "major-heading", "minor-heading"}:
        raise ValueError(f"Unsupported heading tag: {tag}")
    level: Literal["oral", "major", "minor"]
    if tag == "oral-heading":
        level = "oral"
    elif tag == "major-heading":
        level = "major"
    else:
        level = "minor"
    return Heading(
        id=el.attrib.get("id", ""),
        level=level,
        text=_element_text(el),
    )


def _parse_paragraphs(p_nodes: Iterable[ET.Element]) -> list[Paragraph]:
    out: list[Paragraph] = []
    for p in p_nodes:
        if p.tag != "p":
            # Skip non-paragraphs inside a speech just in case
            continue
        pid = p.attrib.get("pid", "")
        qnum = p.attrib.get("qnum")
        classes = p.attrib.get("class", "")
        italic = "italic" in classes.split()
        text = _element_text(p)
        out.append(Paragraph(pid=pid, text=text, italic=italic, qnum=qnum))
    return out


def _parse_speech(el: ET.Element) -> Speech:
    return Speech(
        id=el.attrib.get("id", ""),
        speakername=el.attrib.get("speakername"),
        type=el.attrib.get("type"),
        paragraphs=_parse_paragraphs(el.findall("p")),
    )


def xml_to_blocks(xml_string: str) -> list[Block]:
    """Parse TheyWorkForYou Hansard XML into a list of blocks.

    Blocks are either headings (oral/major/minor) or speeches with paragraphs.
    """
    if not xml_string.strip():
        return []
    root = ET.fromstring(xml_string)
    blocks: list[Block] = []
    for child in root:
        if child.tag in {"oral-heading", "major-heading", "minor-heading"}:
            blocks.append(_parse_heading(child))
        elif child.tag == "speech":
            blocks.append(_parse_speech(child))
        else:
            # Ignore other tags for now
            continue
    return blocks


def blocks_to_markdown(blocks: list[Block]) -> str:
    """Render parsed blocks to a Markdown string.

    - Headings map to Markdown levels:
      oral -> ##, major -> ###, minor -> ####
    - Each speech renders as an ##### heading with the speaker name (or "No speaker")
      and optional type in parentheses, followed by paragraphs with their [pid].
    """
    lines: list[str] = []
    for block in blocks:
        if isinstance(block, Heading):
            if block.level == "oral":
                prefix = "##"
            elif block.level == "major":
                prefix = "###"
            else:
                prefix = "####"
            if block.text:
                lines.append(f"{prefix} {block.text}")
                lines.append("")
        elif isinstance(block, Speech):
            speaker = block.speakername or "No speaker"
            type_suffix = f" ({block.type})" if block.type else ""
            lines.append(f"##### {speaker}{type_suffix}")
            lines.append("")
            for para in block.paragraphs:
                body = para.text
                if para.italic and body:
                    body = f"*{body}*"
                pid = para.pid or ""
                pid_prefix = f"[{pid}] " if pid else ""
                lines.append(f"{pid_prefix}{body}")
                lines.append("")
        else:
            # Should not happen
            continue
    # Trim trailing whitespace lines
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def xml_to_markdown(xml_string: str) -> str:
    """Convenience function: parse XML and render blocks to Markdown."""
    return blocks_to_markdown(xml_to_blocks(xml_string))


def xml_to_topics(xml_string: str) -> list[Topic]:
    """Split debate into topics by major-heading boundaries.

    Groups blocks from each major-heading (or oral-heading) until the next one.
    Returns 5-10 topics per day typically.

    Args:
        xml_string: XML string to parse.

    Returns:
        List of Topic objects, each containing a title and blocks.
    """
    blocks = xml_to_blocks(xml_string)
    if not blocks:
        return []

    topics: list[Topic] = []
    current_topic_blocks: list[Block] = []
    current_title = ""
    current_id = ""

    for block in blocks:
        if isinstance(block, Heading) and block.level in ("oral", "major"):
            if current_topic_blocks:
                speech_count = sum(
                    1 for b in current_topic_blocks if isinstance(b, Speech)
                )
                if speech_count >= 2:
                    topics.append(
                        Topic(
                            id=current_id,
                            title=current_title,
                            blocks=current_topic_blocks,
                        )
                    )
            current_title = block.text
            current_id = block.id
            current_topic_blocks = [block]
        else:
            if not current_topic_blocks:
                current_title = "Untitled"
                current_id = ""
            current_topic_blocks.append(block)

    if current_topic_blocks:
        speech_count = sum(1 for b in current_topic_blocks if isinstance(b, Speech))
        if speech_count >= 2:
            topics.append(
                Topic(id=current_id, title=current_title, blocks=current_topic_blocks)
            )

    return topics
