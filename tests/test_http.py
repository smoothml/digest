"""Tests for the retrying HTTP client."""

import pytest
import requests
import responses
from responses import matchers

from digest.http import MAX_RETRIES, RetryingHttpClient

_URL = "https://example.test/data.xml"


@pytest.mark.parametrize(
    ("timeout", "expected_timeout"),
    [
        pytest.param(None, 60, id="default"),
        pytest.param(5.0, 5.0, id="configured"),
    ],
)
@responses.activate
def test_get_passes_timeout(timeout: float | None, expected_timeout: float) -> None:
    """A GET sends the client's timeout, 60 seconds unless configured."""
    responses.add(
        responses.GET,
        _URL,
        status=200,
        match=[matchers.request_kwargs_matcher({"timeout": expected_timeout})],
    )
    client = (
        RetryingHttpClient() if timeout is None else RetryingHttpClient(timeout=timeout)
    )

    assert client.get(_URL).status_code == requests.codes.ok


@responses.activate
def test_get_retries_server_errors_then_raises() -> None:
    """Server errors are retried up to the configured limit before raising."""
    responses.add(responses.GET, _URL, status=503)

    with pytest.raises(requests.exceptions.RetryError):
        RetryingHttpClient().get(_URL)

    assert len(responses.calls) == MAX_RETRIES + 1
