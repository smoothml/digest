import re
import tomllib
import unicodedata
from datetime import date
from pathlib import Path
from typing import TypedDict, cast

import tomli_w
from loguru import logger

from digest.constants import POST_BASE_PATH_TEMPLATE

_SLUG_STRIP_RE = re.compile(r"[-\s]+")  # Collapse runs of dashes/space
_SLUG_CLEAN_RE = re.compile(
    r"[^\w\s-]"
)  # Drop punctuation (keeps letters, numbers, _, and -)


class Metadata(TypedDict):
    """Metadata for a post."""

    date: date
    draft: bool
    title: str
    tags: list[str]


def get_post_base_path(site: str, section: str | None = None) -> Path:
    """Get the base post path for a site.

    Args:
        site: Name of the site.
        section: Section of the site in which to publish.

    Returns:
        Base post path for the site.
    """
    path = Path(POST_BASE_PATH_TEMPLATE.safe_substitute(site=site))
    if section:
        path = path / section
    return path


def format_post(content: str, dt: date, title: str, tags: list[str]) -> str:
    """Format a digest post.

    Args:
        content: Content of the post.
        dt: Date of the post.
        title: Title of the post.
        tags: Tags for the post.

    Returns:
        Formatted post.
    """
    frontmatter = tomli_w.dumps(
        {
            "date": str(dt),
            "draft": False,
            "title": title,
            "tags": tags,
        }
    ).strip()
    return f"+++\n{frontmatter}\n+++\n\n{content}".strip()


def create_post(
    site: str, content: str, post_path: str, section: str | None = None
) -> None:
    """Create a new post.

    Args:
        content: Content of the post.
        post_path: Path to the post.
    """
    path = get_post_base_path(site, section) / post_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write(content)


def read_post_metadata(path: Path) -> Metadata:
    """Read metadata from a post.

    Args:
        path: Path to the post.

    Returns:
        Dictionary of metadata.
    """
    with path.open("r", encoding="utf-8") as f:
        content = f.read()

    data = tomllib.loads(content.lstrip("+").split("+++")[0].strip())
    metadata = cast(Metadata, data)
    return metadata


def get_all_tags(site: str) -> set[str]:
    """Get unique tags from all posts in a directory.

    Args:
        dir: Directory containing posts.

    Returns:
        Set of unique tags.
    """
    dir_path = get_post_base_path(site)
    if not dir_path.exists():
        raise ValueError(f"Path {dir_path} does not exist")
    if not dir_path.is_dir():
        raise ValueError(f"Path {dir_path} is not a directory")
    tags: set[str] = set()
    for path in dir_path.glob("**/*.md"):
        try:
            metadata = read_post_metadata(path)
        except tomllib.TOMLDecodeError:
            logger.warning(f"Skipping post with malformed frontmatter: {path}")
            continue
        tags.update(metadata.get("tags", []))
    return tags


def slugify(
    text: str, *, allow_unicode: bool = False, max_length: int | None = 100
) -> str:
    """Convert text to a URL slug.

    Performs the following:
    - lowercases
    - strips accents (unless allow_unicode=True)
    - removes punctuation
    - collapses whitespace/dashes to single '-'
    - trims leading/trailing '-'
    - Optionally truncates to `max_length`

    Args:
        title: Title to convert.

    Returns:
        Slug string.
    """
    text = str(text)

    if len(text) == 0:
        logger.warning("Empty string provided to slugify")
        return text

    # Normalize & (optionally) strip accents to ASCII
    if allow_unicode:
        text = unicodedata.normalize("NFKC", text)
    else:
        text = (
            unicodedata.normalize("NFKD", text)
            .encode("ascii", "ignore")
            .decode("ascii")
        )

    text = text.lower()
    text = _SLUG_CLEAN_RE.sub("", text)  # Remove punctuation
    text = _SLUG_STRIP_RE.sub("-", text).strip("-_")  # Collapse to '-' and trim

    if max_length is not None:
        text = text[:max_length].rstrip("-")  # Avoid trailing '-' after truncation

    return text
