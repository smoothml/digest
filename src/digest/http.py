from typing import Final

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REQUEST_TIMEOUT_SECONDS: Final = 60
MAX_RETRIES: Final = 3
RETRY_BACKOFF_FACTOR: Final = 1.0
RETRY_STATUS_FORCELIST: Final = (500, 502, 503, 504)


def _build_retry(
    max_retries: int,
    backoff_factor: float,
    status_forcelist: tuple[int, ...],
) -> Retry:
    """Build a retry policy for idempotent GET requests.

    Transient failures (connection errors, read/connect timeouts, and the server
    errors in ``status_forcelist``) are retried up to ``max_retries`` times with
    an exponential backoff governed by ``backoff_factor``.

    Args:
        max_retries: Maximum number of retries after the initial attempt.
        backoff_factor: Exponential backoff factor between retries.
        status_forcelist: HTTP status codes that should trigger a retry.

    Returns:
        The configured urllib3 retry policy.
    """
    return Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=frozenset({"GET"}),
    )


class RetryingHttpClient:
    """An HTTP client that retries transient failures with exponential backoff.

    The client only fetches and retries; it raises on final failure and leaves
    callers to decide what a failure means.
    """

    def __init__(
        self,
        *,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
        max_retries: int = MAX_RETRIES,
        backoff_factor: float = RETRY_BACKOFF_FACTOR,
        status_forcelist: tuple[int, ...] = RETRY_STATUS_FORCELIST,
    ) -> None:
        """Initialize the client.

        Args:
            timeout: Per-request timeout in seconds.
            max_retries: Maximum number of retries after the initial attempt.
            backoff_factor: Exponential backoff factor between retries.
            status_forcelist: HTTP status codes that should trigger a retry.
        """
        self._timeout = timeout
        self._session = requests.Session()
        adapter = HTTPAdapter(
            max_retries=_build_retry(max_retries, backoff_factor, status_forcelist)
        )
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def get(self, url: str) -> requests.Response:
        """Perform a GET request with the configured timeout and retries.

        Args:
            url: The URL to fetch.

        Returns:
            The HTTP response.

        Raises:
            requests.exceptions.RequestException: If the request still fails
                after exhausting all retry attempts.
        """
        return self._session.get(url, timeout=self._timeout)
