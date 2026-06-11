import importlib
import tomllib
from datetime import date
from pathlib import Path

import pytest


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
    site_mod = importlib.import_module("digest.site")
    post = site_mod.format_post("Body text.", date(2025, 1, 1), title, ["energy"])

    block = post.lstrip("+").split("+++")[0].strip()
    data = tomllib.loads(block)

    assert data["title"] == title


def test_read_post_metadata_returns_title_with_embedded_quote(tmp_path: Path) -> None:
    """read_post_metadata round-trips a title containing a double quote unchanged."""
    site_mod = importlib.import_module("digest.site")
    title = 'Commons Debates "Net Zero" Strategy'
    post = site_mod.format_post("Body text.", date(2025, 1, 1), title, ["energy"])
    path = tmp_path / "post.md"
    path.write_text(post, encoding="utf-8")

    metadata = site_mod.read_post_metadata(path)

    assert metadata["title"] == title
    assert metadata["tags"] == ["energy"]


def test_format_post_tags_with_apostrophe_round_trip() -> None:
    """Tags containing quote characters serialise to valid TOML."""
    site_mod = importlib.import_module("digest.site")
    post = site_mod.format_post(
        "Body text.", date(2025, 1, 1), "Title", ["children's", "net-zero"]
    )

    block = post.lstrip("+").split("+++")[0].strip()
    data = tomllib.loads(block)

    assert data["tags"] == ["children's", "net-zero"]


def test_get_all_tags_skips_malformed_post(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A single malformed post must not abort tag collection for the site."""
    site_mod = importlib.import_module("digest.site")
    monkeypatch.setattr(site_mod, "get_post_base_path", lambda site: tmp_path)

    good = site_mod.format_post("Body.", date(2025, 1, 1), "Good", ["alpha", "beta"])
    (tmp_path / "good.md").write_text(good, encoding="utf-8")
    (tmp_path / "bad.md").write_text(
        '+++\ntitle = "Broken "quote" title"\n+++\n\nBody.', encoding="utf-8"
    )

    tags = site_mod.get_all_tags("hansard")

    assert tags == {"alpha", "beta"}


def test_slugify_basic_ascii() -> None:
    """Convert a simple ASCII title into a clean, dashed, lowercase slug."""
    site_mod = importlib.import_module("digest.site")
    assert site_mod.slugify("Hello, World!") == "hello-world"


def test_slugify_collapse_whitespace_and_dashes() -> None:
    """Collapse runs of spaces and hyphens to a single hyphen."""
    site_mod = importlib.import_module("digest.site")
    text = "A    B---C   D"
    assert site_mod.slugify(text) == "a-b-c-d"


def test_slugify_preserves_inner_underscores_and_trims_edges() -> None:
    """Preserve inner underscores but trim leading/trailing underscores."""
    site_mod = importlib.import_module("digest.site")
    text = "  __Hello__World__  "
    assert site_mod.slugify(text) == "hello__world"


def test_slugify_removes_punctuation() -> None:
    """Remove punctuation characters not in [_-] and collapse to hyphens."""
    site_mod = importlib.import_module("digest.site")
    text = "C# & C++: The sequel"
    assert site_mod.slugify(text) == "c-c-the-sequel"


def test_slugify_allow_unicode_true_preserves_non_ascii() -> None:
    """When allow_unicode=True, keep Unicode letters (e.g., accents, CJK)."""
    site_mod = importlib.import_module("digest.site")
    text = "Café ångström 日本語"
    assert site_mod.slugify(text, allow_unicode=True) == "café-ångström-日本語"


def test_slugify_allow_unicode_false_strips_to_ascii() -> None:
    """When allow_unicode=False, strip accents and non-ASCII characters."""
    site_mod = importlib.import_module("digest.site")
    text = "Café ångström"
    assert site_mod.slugify(text, allow_unicode=False) == "cafe-angstrom"


def test_slugify_non_ascii_only_with_spaces_becomes_empty_when_ascii_only() -> None:
    """If all letters are non-ASCII and allow_unicode=False, result is empty."""
    site_mod = importlib.import_module("digest.site")
    text = "中文 标题"
    # After ASCII normalization these become spaces, which collapse to '-' then strip to ''
    assert site_mod.slugify(text, allow_unicode=False) == ""


def test_slugify_default_max_length_is_100() -> None:
    """Default max_length=100 truncates long slugs to 100 characters."""
    site_mod = importlib.import_module("digest.site")
    text = "a" * 150
    result = site_mod.slugify(text)
    assert len(result) == 100
    assert result == "a" * 100


def test_slugify_max_length_none_disables_truncation() -> None:
    """max_length=None disables truncation entirely."""
    site_mod = importlib.import_module("digest.site")
    text = "a" * 150
    result = site_mod.slugify(text, max_length=None)
    assert len(result) == 150
    assert result == "a" * 150


def test_slugify_truncation_does_not_leave_trailing_hyphen() -> None:
    """Ensure rstrip('-') runs after truncation to avoid ending with a hyphen."""
    site_mod = importlib.import_module("digest.site")
    text = ("a" * 50) + " " + ("b" * 60)
    # Collapses to 'a'*50 + '-' + 'b'*60 (length 111). Cut at 51 to land on '-'.
    result = site_mod.slugify(text, max_length=51)
    assert result == "a" * 50
    assert not result.endswith("-")


def test_slugify_empty_string_logs_warning_and_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty input should log a warning and return an empty string.

    The implementation references a module-level ``logger``. We inject a minimal
    stub so the call path is exercised without depending on external logging
    configuration.
    """
    site_mod = importlib.import_module("digest.site")

    class StubLogger:
        def __init__(self) -> None:
            self.messages: list[tuple[str, str]] = []

        def warning(self, msg: str) -> None:  # noqa: D401 - simple capture
            # Capture warning-level messages
            self.messages.append(("warning", msg))

    stub = StubLogger()
    # Allow setting even if attribute is absent in the module.
    monkeypatch.setattr(site_mod, "logger", stub, raising=False)

    assert site_mod.slugify("") == ""
    assert ("warning", "Empty string provided to slugify") in stub.messages
