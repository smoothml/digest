"""Tests for the Hansard data source content retrieval and lifecycle."""

from collections.abc import Callable
from datetime import date
from string import ascii_lowercase
from unittest.mock import MagicMock

import pytest
import requests

from digest.cache import DataCache
from digest.http import RetryingHttpClient
from digest.sources.hansard.constants import HansardSourceType
from digest.sources.hansard.main import Debate, HansardDataSource

_TEST_DATE = date(2025, 9, 1)
_FALLBACK_WARNING = "No version flagged latest"


def _xml(version: str, *, latest: bool) -> bytes:
    flag = "yes" if latest else "no"
    return f'<publicwhip latest="{flag}"><minor id="{version}" /></publicwhip>'.encode()


def _make_response(status_code: int, content: bytes) -> MagicMock:
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.content = content
    return response


def _make_404_response() -> MagicMock:
    response = _make_response(requests.codes.not_found, b"")
    error = requests.exceptions.HTTPError("404 Not Found")
    error.response = response
    response.raise_for_status.side_effect = error
    return response


def _make_source(http_client: MagicMock) -> HansardDataSource:
    return HansardDataSource(
        data_cache=DataCache("memory://hansard-test"), http_client=http_client
    )


@pytest.mark.parametrize(
    ("bodies", "expected_version", "warns"),
    [
        ([_xml("a", latest=True)], "a", False),
        ([_xml("a", latest=False), _xml("b", latest=True)], "b", False),
        ([_xml("a", latest=False), None], "a", True),
        ([_xml(version, latest=False) for version in ascii_lowercase], "z", True),
    ],
    ids=["latest-first", "latest-later", "404-after-non-latest", "versions-exhausted"],
)
def test_get_returns_newest_available_version(
    bodies: list[bytes | None],
    expected_version: str,
    warns: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Version probing returns the latest-flagged version, or the last one fetched."""
    http_client = MagicMock(spec=RetryingHttpClient)
    http_client.get.side_effect = [
        _make_404_response()
        if body is None
        else _make_response(requests.codes.ok, body)
        for body in bodies
    ]
    source = _make_source(http_client)

    debate = source.get(_TEST_DATE, HansardSourceType.COMMONS, refresh=True)

    assert debate.exists is True
    assert debate.fetch_failed is False
    assert f'id="{expected_version}"' in debate.xml_string
    assert http_client.get.call_count == len(bodies)
    assert (_FALLBACK_WARNING in caplog.text) is warns


@pytest.mark.parametrize(
    ("make_outcome", "fetch_failed"),
    [
        pytest.param(_make_404_response, False, id="404"),
        pytest.param(lambda: requests.exceptions.Timeout("boom"), True, id="timeout"),
        pytest.param(
            lambda: _make_response(
                requests.codes.ok, b"<html><body>Down for maintenance</body>"
            ),
            True,
            id="unparseable-body",
        ),
        pytest.param(
            lambda: _make_response(requests.codes.ok, b"\xff\xfenot utf-8 content"),
            True,
            id="non-utf8-body",
        ),
    ],
)
def test_get_reports_missing_debate(
    make_outcome: Callable[[], MagicMock | requests.exceptions.RequestException],
    fetch_failed: bool,
) -> None:
    """A failed fetch yields no debate, flagged as a fetch failure unless a 404."""
    http_client = MagicMock(spec=RetryingHttpClient)
    http_client.get.side_effect = [make_outcome()]
    source = _make_source(http_client)

    debate = source.get(_TEST_DATE, HansardSourceType.COMMONS, refresh=True)

    assert debate.exists is False
    assert debate.fetch_failed is fetch_failed
    assert debate.xml_string == ""


def test_debate_to_markdown_renders_xml(sample_debate_xml: str) -> None:
    """A debate renders its stored XML through the Markdown parser."""
    debate = Debate(
        date=_TEST_DATE,
        source=HansardSourceType.COMMONS,
        xml_string=sample_debate_xml,
        exists=True,
    )

    md = debate.to_markdown()

    assert "### Work and Pensions" in md
    assert "[c1.5/1] The unemployment rate is 4.7%" in md


def test_debate_to_markdown_is_empty_without_xml() -> None:
    """A debate with no stored XML renders as an empty document."""
    debate = Debate(date=_TEST_DATE, source=HansardSourceType.COMMONS, xml_string="")

    assert debate.to_markdown() == ""
