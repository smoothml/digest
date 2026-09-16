"""Tests for the Hansard data source content retrieval and lifecycle."""

from datetime import date
from string import ascii_lowercase
from unittest.mock import MagicMock

import pytest
import requests

from digest.cache import DataCache
from digest.http import RetryingHttpClient
from digest.sources.hansard.constants import HansardSourceType
from digest.sources.hansard.main import HansardDataSource

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


def test_get_reports_absence_without_fetch_failed_on_404() -> None:
    """A 404 is reported as a genuinely absent report, not a fetch failure."""
    http_client = MagicMock(spec=RetryingHttpClient)
    http_client.get.return_value = _make_404_response()
    source = _make_source(http_client)

    debate = source.get(_TEST_DATE, HansardSourceType.COMMONS, refresh=True)

    assert debate.exists is False
    assert debate.fetch_failed is False
    assert debate.xml_string == ""


@pytest.mark.parametrize(
    "error",
    [
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.RetryError,
    ],
)
def test_get_marks_fetch_failed_on_transient_error(
    error: type[requests.exceptions.RequestException],
) -> None:
    """Transient failures are handled as missing data and flagged as fetch failures."""
    http_client = MagicMock(spec=RetryingHttpClient)
    http_client.get.side_effect = error("boom")
    source = _make_source(http_client)

    debate = source.get(_TEST_DATE, HansardSourceType.COMMONS, refresh=True)

    assert debate.exists is False
    assert debate.fetch_failed is True
    assert debate.xml_string == ""


@pytest.mark.parametrize(
    "content",
    [
        b"<html><body>Down for maintenance</body>",
        b"\xff\xfenot utf-8 content",
    ],
)
def test_get_marks_fetch_failed_on_malformed_body(content: bytes) -> None:
    """A 200 with an unparseable or non-UTF-8 body is flagged as a fetch failure."""
    http_client = MagicMock(spec=RetryingHttpClient)
    http_client.get.return_value = _make_response(requests.codes.ok, content)
    source = _make_source(http_client)

    debate = source.get(_TEST_DATE, HansardSourceType.COMMONS, refresh=True)

    assert debate.exists is False
    assert debate.fetch_failed is True
    assert debate.xml_string == ""
