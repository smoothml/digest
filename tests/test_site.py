import tomllib
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from digest.site import format_post, get_all_tags, read_post_metadata, slugify


@pytest.fixture
def site_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every site's post directory at a temporary directory.

    Args:
        tmp_path: The built-in temporary directory fixture.
        monkeypatch: The built-in monkeypatch fixture.

    Returns:
        The temporary post directory.
    """
    monkeypatch.setattr("digest.site.get_post_base_path", lambda site: tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    "title",
    [
        pytest.param('Commons Debates "Net Zero" Strategy', id="embedded-quote"),
        pytest.param('"Commons Backs Net Zero Plan"', id="model-wrapped-quotes"),
        pytest.param(r"Backslash C:\Users\test", id="backslash"),
        pytest.param("Lords Strengthen Victims' Rights", id="apostrophe"),
    ],
)
def test_read_post_metadata_round_trips_format_post(tmp_path: Path, title: str) -> None:
    """A formatted post reads back with its metadata intact and the date as a date."""
    post = format_post("Body text.", date(2025, 1, 1), title, ["children's", "energy"])
    path = tmp_path / "post.md"
    path.write_text(post, encoding="utf-8")

    metadata = read_post_metadata(path)

    assert metadata == {
        "date": date(2025, 1, 1),
        "draft": False,
        "title": title,
        "tags": ["children's", "energy"],
    }


@pytest.mark.parametrize(
    "frontmatter",
    [
        pytest.param('title = "Broken "quote" title"', id="invalid-toml"),
        pytest.param('title = "Invalid"\ntags = "gamma"', id="invalid-schema"),
    ],
)
def test_get_all_tags_skips_malformed_post(
    site_dir: Path, caplog: pytest.LogCaptureFixture, frontmatter: str
) -> None:
    """A malformed post is skipped with a warning rather than aborting collection."""

    good = format_post("Body.", date(2025, 1, 1), "Good", ["alpha", "beta"])
    (site_dir / "good.md").write_text(good, encoding="utf-8")
    (site_dir / "bad.md").write_text(
        f"+++\n{frontmatter}\n+++\n\nBody.", encoding="utf-8"
    )

    tags = get_all_tags("hansard")

    assert tags == {"alpha", "beta"}
    assert "Skipping post with malformed frontmatter" in caplog.text


@pytest.mark.parametrize(
    ("text", "allow_unicode", "max_length", "expected"),
    [
        pytest.param("Hello, World!", False, 100, "hello-world", id="basic-ascii"),
        pytest.param("A    B---C   D", False, 100, "a-b-c-d", id="collapse-separators"),
        pytest.param(
            "  __Hello__World__  ",
            False,
            100,
            "hello__world",
            id="trim-edge-underscores",
        ),
        pytest.param(
            "C# & C++: The sequel", False, 100, "c-c-the-sequel", id="punctuation"
        ),
        pytest.param(
            "Café ångström 日本語", True, 100, "café-ångström-日本語", id="unicode-kept"
        ),
        pytest.param(
            "Café ångström", False, 100, "cafe-angstrom", id="unicode-stripped"
        ),
        pytest.param("中文 标题", False, 100, "", id="non-ascii-only-empties"),
        pytest.param("a" * 150, False, None, "a" * 150, id="no-max-length"),
        pytest.param(
            ("a" * 50) + " " + ("b" * 60),
            False,
            51,
            "a" * 50,
            id="truncation-trims-trailing-hyphen",
        ),
    ],
)
def test_slugify(
    text: str, allow_unicode: bool, max_length: int | None, expected: str
) -> None:
    """Slugify lowercases, strips punctuation, collapses separators and truncates."""
    assert slugify(text, allow_unicode=allow_unicode, max_length=max_length) == expected


def test_slugify_truncates_to_100_characters_by_default() -> None:
    """Slugs are capped at 100 characters unless told otherwise."""
    assert slugify("a" * 150) == "a" * 100


def test_slugify_empty_string_logs_warning_and_returns_empty(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Empty input logs a warning and returns an empty string."""
    assert slugify("") == ""
    assert "Empty string provided to slugify" in caplog.text


@pytest.mark.parametrize(
    ("frontmatter", "error"),
    [
        pytest.param(
            'title = "Broken "quote" title"', tomllib.TOMLDecodeError, id="toml"
        ),
        pytest.param('title = "Title"\ntags = "energy"', ValidationError, id="schema"),
    ],
)
def test_read_post_metadata_rejects_malformed_frontmatter(
    tmp_path: Path, frontmatter: str, error: type[Exception]
) -> None:
    """Frontmatter that is not TOML, or does not match the schema, is rejected."""
    path = tmp_path / "post.md"
    path.write_text(f"+++\n{frontmatter}\n+++\n\nBody.", encoding="utf-8")

    with pytest.raises(error):
        read_post_metadata(path)


def test_get_all_tags_ignores_section_index_pages(
    site_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Section index pages are not posts, so they are never read or warned about."""

    good = format_post("Body.", date(2025, 1, 1), "Good", ["alpha"])
    (site_dir / "good.md").write_text(good, encoding="utf-8")
    (site_dir / "_index.md").write_text(
        '+++\ntitle = "Commons"\nmenu = "main"\nweight = 3\n+++\n', encoding="utf-8"
    )
    (site_dir / "commons").mkdir()
    (site_dir / "commons" / "_index.md").write_text(
        '+++\ntitle = "Commons"\nweight = 3\n+++\n', encoding="utf-8"
    )

    tags = get_all_tags("hansard")

    assert tags == {"alpha"}
    assert caplog.text == ""
