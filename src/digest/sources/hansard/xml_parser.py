from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class Paragraph:
    pid: str
    text: str
    italic: bool = False
    qnum: str | None = None


@dataclass(frozen=True)
class Speech:
    id: str
    speakername: str | None
    type: str | None
    paragraphs: list[Paragraph]


@dataclass(frozen=True)
class Heading:
    id: str
    level: Literal["oral", "major", "minor"]
    text: str


Block = Speech | Heading


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
