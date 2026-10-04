"""Tests for the retrying HTTP client."""

from unittest.mock import MagicMock, patch

import pytest
import requests
import responses

from digest.http import (
    MAX_RETRIES,
    RETRY_BACKOFF_FACTOR,
    RETRY_STATUS_FORCELIST,
    RetryingHttpClient,
    _build_retry,
)

_URL = "https://example.test/data.xml"


def _make_ok_response() -> MagicMock:
    response = MagicMock(spec=requests.Response)
    response.status_code = requests.codes.ok
    response.content = b"<ok/>"
    return response


def test_build_retry_configures_bounded_exponential_backoff() -> None:
    """The retry policy is bounded, backs off exponentially, and is GET-only."""
    retry = _build_retry(MAX_RETRIES, RETRY_BACKOFF_FACTOR, RETRY_STATUS_FORCELIST)

    assert retry.total == MAX_RETRIES
    assert retry.backoff_factor == RETRY_BACKOFF_FACTOR
    assert retry.status_forcelist == RETRY_STATUS_FORCELIST
    assert retry.allowed_methods == frozenset({"GET"})


@pytest.mark.parametrize(
    ("client", "expected_timeout"),
    [
        pytest.param(RetryingHttpClient(), 60, id="default"),
        pytest.param(RetryingHttpClient(timeout=5), 5, id="configured"),
    ],
)
def test_get_passes_timeout(client: RetryingHttpClient, expected_timeout: int) -> None:
    """A GET passes the client's timeout, 60 seconds unless configured, to the session."""
    with patch.object(
        client._session, "get", return_value=_make_ok_response()
    ) as mock_get:
        client.get(_URL)

    assert mock_get.call_args.kwargs["timeout"] == expected_timeout


@responses.activate
def test_get_retries_transient_server_errors_then_returns_response() -> None:
    """Transient server errors are retried and the eventual response is returned."""
    responses.add(responses.GET, _URL, status=503)
    responses.add(responses.GET, _URL, status=503)
    responses.add(responses.GET, _URL, body="<ok/>", status=200)

    response = RetryingHttpClient().get(_URL)

    assert response.status_code == requests.codes.ok
    assert len(responses.calls) == 3


@responses.activate
def test_get_raises_after_exhausting_retries() -> None:
    """A persistently failing endpoint raises once retries are exhausted."""
    responses.add(responses.GET, _URL, status=503)

    with pytest.raises(requests.exceptions.RetryError):
        RetryingHttpClient().get(_URL)

    assert len(responses.calls) == MAX_RETRIES + 1


@pytest.mark.parametrize(
    "error",
    [requests.exceptions.Timeout, requests.exceptions.ConnectionError],
)
@responses.activate
def test_get_propagates_transient_request_errors(
    error: type[requests.exceptions.RequestException],
) -> None:
    """Connection errors and timeouts are propagated, not swallowed."""
    responses.add(responses.GET, _URL, body=error("boom"))

    with pytest.raises(error):
        RetryingHttpClient().get(_URL)
