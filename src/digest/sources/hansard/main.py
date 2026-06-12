from datetime import date
from string import ascii_lowercase
from typing import override
from xml.etree import ElementTree

import requests
from loguru import logger
from pydantic import BaseModel

from digest.cache import DataCache
from digest.http import RetryingHttpClient
from digest.sources.base import BaseDataSource
from digest.sources.hansard.constants import BASE_URL, FILE_PREFIXES, HansardSourceType
from digest.sources.hansard.xml_parser import xml_to_markdown


def _is_absent(error: BaseException) -> bool:
    """Return whether a fetch error represents a genuinely absent report.

    A 404 means no report was published for the date; any other error
    (timeout, connection failure, exhausted retries, malformed response)
    represents a failure to determine whether a report exists.

    Args:
        error: The exception raised while fetching content.

    Returns:
        True if the error indicates an absent report, False otherwise.
    """
    return (
        isinstance(error, requests.exceptions.HTTPError)
        and error.response is not None
        and error.response.status_code == requests.codes.not_found
    )


class Debate(BaseModel):
    """Debate."""

    date: date
    source: HansardSourceType
    xml_string: str
    exists: bool = False
    fetch_failed: bool = False

    def to_markdown(self) -> str:
        """Render the underlying Hansard XML as a Markdown document.

        Maintains association between paragraph text, paragraph IDs, and
        speaker names by delegating to the XML parser utilities.

        Returns:
            A Markdown string representation of the debate.
        """
        if not self.xml_string:
            return ""
        return xml_to_markdown(self.xml_string)


class HansardDataSource(BaseDataSource[[date, HansardSourceType, bool], Debate]):
    """Hansard data source class.

    Agent to download parse Hansard reports extracted by TheyWorkForYou
    (https://www.theyworkforyou.com).
    """

    name: str = "hansard"

    def __init__(
        self,
        data_cache: DataCache | None = None,
        http_client: RetryingHttpClient | None = None,
    ) -> None:
        """Initialize the Hansard data source.

        Args:
            data_cache: Optional data cache backend.
            http_client: Optional HTTP client used to fetch reports.
        """
        super().__init__(data_cache)
        self._http = http_client or RetryingHttpClient()

    @override
    def get(self, dt: date, source: HansardSourceType, refresh: bool = False) -> Debate:
        """Extract Hansard report for a specific date.

        Args:
            dt: Date to extract Hansard report for.
            source: Source to extract Hansard report from.
            refresh: Whether to refresh the cache.

        Returns:
            Debate object containing the extracted Hansard report.
        """
        cache_path = self.name + "/" + self._get_cache_path(dt, source)
        if refresh or not self._exists_in_cache(cache_path):
            fetch_failed = False
            try:
                content = self._get_content(dt, source)
                exists = True
            except (
                requests.exceptions.RequestException,
                ElementTree.ParseError,
                UnicodeDecodeError,
            ) as e:
                logger.warning(f"Failed to get content for {dt} {source}: {e}")
                content = ""
                exists = False
                fetch_failed = not _is_absent(e)
            debate = Debate(
                date=dt,
                source=source,
                xml_string=content,
                exists=exists,
                fetch_failed=fetch_failed,
            )
            if debate.exists:
                self._store_to_cache(cache_path, debate.xml_string)
        else:
            debate = Debate(
                date=dt,
                source=source,
                xml_string=str(self._read_from_cache(cache_path)),
                exists=True,
            )
        return debate

    def _get_cache_path(self, dt: date, source: HansardSourceType) -> str:
        """Get cache path for a specific date.

        Args:
            dt: Date to get cache path for.
            source: Source to get cache path for.

        Returns:
            Cache path for the given date.
        """
        return f"{dt}-{source}.xml"

    def _get_url_path(
        self, dt: date, source: HansardSourceType, version: str = "a"
    ) -> str:
        """Get URL path for a specific source and date.

        Args:
            dt: Date to get path for.
            source: Source to get path for.
            version: Version for which to get the URL path.

        Returns:
            URL path for the given source and date.
        """
        if version not in ascii_lowercase:
            raise ValueError("version must be a single lowercase letter")
        return f"{source}/{FILE_PREFIXES[source]}{dt.strftime('%Y-%m-%d')}{version}.xml"

    def _get_content(self, dt: date, source: HansardSourceType) -> str:
        """Get content for a specific source and date.

        Args:
            dt: Date to get content for.
            source: Source to get content for.

        Returns:
            String containing the raw XML content.
        """
        content_found = False
        failed = False
        version_idx = 0
        response_str = ""
        while not content_found and not failed:
            path = self._get_url_path(dt, source, ascii_lowercase[version_idx])
            response = self._http.get(f"{BASE_URL}/{path}")
            if response.status_code == requests.codes.not_found:
                # Mark interaction as failed if no content found.
                failed = True
                if not content_found:
                    # If no earlier versions found, raise.
                    response.raise_for_status()
            elif response.status_code == requests.codes.ok:
                # If content is found, parse it.
                response_str = response.content.strip().decode("utf-8")
                root = ElementTree.fromstring(response_str)
                if root.attrib.get("latest") == "yes":
                    content_found = True
                else:
                    version_idx += 1
                    if version_idx >= len(ascii_lowercase):
                        failed = True
            else:
                response.raise_for_status()
        if failed and content_found:
            logger.warning(
                f"Latest version not found for {source} on {dt}. Returning latest version."
            )
        return response_str


def get_hansard_data_source() -> HansardDataSource:
    return HansardDataSource()
