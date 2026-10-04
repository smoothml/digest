import tomllib
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from digest.site import format_post, get_all_tags, read_post_metadata, slugify


@pytest.mark.parametrize(
    "title",
    [
        pytest.param('Commons Debates "Net Zero" Strategy', id="embedded-quote"),
        pytest.param('"Commons Backs Net Zero Plan"', id="model-wrapped-quotes"),
        pytest.param(r"Backslash C:\Users\test", id="backslash"),
        pytest.param("Lords Strengthen Victims' Rights", id="apostrophe"),
    ],
)
def test_format_post_title_round_trips_through_tomllib(title: str) -> None:
    """A title with TOML-significant characters yields parseable frontmatter."""
    post = format_post("Body text.", date(2025, 1, 1), title, ["energy"])

    block = post.lstrip("+").split("+++")[0].strip()
    data = tomllib.loads(block)

    assert data["title"] == title


def test_read_post_metadata_returns_title_with_embedded_quote(tmp_path: Path) -> None:
    """read_post_metadata round-trips a title containing a double quote unchanged."""
    title = 'Commons Debates "Net Zero" Strategy'
    post = format_post("Body text.", date(2025, 1, 1), title, ["energy"])
    path = tmp_path / "post.md"
    path.write_text(post, encoding="utf-8")

    metadata = read_post_metadata(path)

    assert metadata["title"] == title
    assert metadata["tags"] == ["energy"]


def test_format_post_tags_with_apostrophe_round_trip() -> None:
    """Tags containing quote characters serialise to valid TOML."""
    post = format_post(
        "Body text.", date(2025, 1, 1), "Title", ["children's", "net-zero"]
    )

    block = post.lstrip("+").split("+++")[0].strip()
    data = tomllib.loads(block)

    assert data["tags"] == ["children's", "net-zero"]


@pytest.mark.parametrize(
    "frontmatter",
    [
        pytest.param('title = "Broken "quote" title"', id="invalid-toml"),
        pytest.param('title = "Invalid"\ntags = "gamma"', id="invalid-schema"),
    ],
)
def test_get_all_tags_skips_malformed_post(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    frontmatter: str,
) -> None:
    """A malformed post is skipped with a warning rather than aborting collection."""
    monkeypatch.setattr("digest.site.get_post_base_path", lambda site: tmp_path)

    good = format_post("Body.", date(2025, 1, 1), "Good", ["alpha", "beta"])
    (tmp_path / "good.md").write_text(good, encoding="utf-8")
    (tmp_path / "bad.md").write_text(
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


def test_read_post_metadata_coerces_date_string_to_date(tmp_path: Path) -> None:
    """Frontmatter serialises the date as a string; reading returns a date."""
    post = format_post("Body text.", date(2025, 1, 1), "Title", ["energy"])
    path = tmp_path / "post.md"
    path.write_text(post, encoding="utf-8")

    metadata = read_post_metadata(path)

    assert metadata["date"] == date(2025, 1, 1)


@pytest.mark.parametrize(
    "frontmatter",
    [
        pytest.param('title = "Title"\ntags = "energy"', id="tags-not-a-list"),
        pytest.param('title = "Title"\ntags = [1, 2]', id="tags-not-strings"),
        pytest.param('title = "Title"\ndraft = "maybe"', id="draft-not-a-bool"),
        pytest.param('title = "Title"\ndate = "not-a-date"', id="date-unparseable"),
        pytest.param('draft = false\ntitle = "Title"\ntags = []', id="date-missing"),
        pytest.param(
            'date = 2025-01-01\ntitle = "Title"\ntags = []', id="draft-missing"
        ),
        pytest.param("date = 2025-01-01\ndraft = false\ntags = []", id="title-missing"),
        pytest.param(
            'date = 2025-01-01\ndraft = false\ntitle = "Title"', id="tags-missing"
        ),
        pytest.param('title = "Commons"\nmenu = "main"\nweight = 3', id="index-page"),
    ],
)
def test_read_post_metadata_rejects_invalid_frontmatter(
    tmp_path: Path, frontmatter: str
) -> None:
    """Frontmatter that does not match the metadata schema is rejected."""
    path = tmp_path / "post.md"
    path.write_text(f"+++\n{frontmatter}\n+++\n\nBody.", encoding="utf-8")

    with pytest.raises(ValidationError):
        read_post_metadata(path)


def test_get_all_tags_ignores_section_index_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Section index pages are not posts, so they are never read or warned about."""
    monkeypatch.setattr("digest.site.get_post_base_path", lambda site: tmp_path)

    good = format_post("Body.", date(2025, 1, 1), "Good", ["alpha"])
    (tmp_path / "good.md").write_text(good, encoding="utf-8")
    (tmp_path / "_index.md").write_text(
        '+++\ntitle = "Commons"\nmenu = "main"\nweight = 3\n+++\n', encoding="utf-8"
    )
    (tmp_path / "commons").mkdir()
    (tmp_path / "commons" / "_index.md").write_text(
        '+++\ntitle = "Commons"\nweight = 3\n+++\n', encoding="utf-8"
    )

    tags = get_all_tags("hansard")

    assert tags == {"alpha"}
    assert caplog.text == ""
