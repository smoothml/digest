"""Tests for the Hansard data source content retrieval and lifecycle."""

from datetime import date
from unittest.mock import MagicMock

import pytest
import requests

from digest.cache import DataCache
from digest.http import RetryingHttpClient
from digest.sources.hansard.constants import HansardSourceType
from digest.sources.hansard.main import HansardDataSource

_OK_XML = b'<publicwhip latest="yes"><minor /></publicwhip>'
_TEST_DATE = date(2025, 9, 1)


def _make_response(status_code: int, content: bytes) -> MagicMock:
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.content = content
    return response


def _make_ok_response() -> MagicMock:
    return _make_response(requests.codes.ok, _OK_XML)


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


def test_get_returns_content_on_success() -> None:
    """A successful fetch is parsed and returned as an existing debate."""
    http_client = MagicMock(spec=RetryingHttpClient)
    http_client.get.return_value = _make_ok_response()
    source = _make_source(http_client)

    debate = source.get(_TEST_DATE, HansardSourceType.COMMONS, refresh=True)

    assert debate.exists is True
    assert debate.fetch_failed is False
    assert 'latest="yes"' in debate.xml_string


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
