"""Tests for the retrying HTTP client."""

from unittest.mock import MagicMock, patch

import pytest
import requests
import responses

from digest.http import MAX_RETRIES, RetryingHttpClient

_URL = "https://example.test/data.xml"


def _make_ok_response() -> MagicMock:
    response = MagicMock(spec=requests.Response)
    response.status_code = requests.codes.ok
    response.content = b"<ok/>"
    return response


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
def test_get_retries_server_errors_then_raises() -> None:
    """Server errors are retried up to the configured limit before raising."""
    responses.add(responses.GET, _URL, status=503)

    with pytest.raises(requests.exceptions.RetryError):
        RetryingHttpClient().get(_URL)

    assert len(responses.calls) == MAX_RETRIES + 1
