from datetime import date
from string import ascii_lowercase
from xml.etree import ElementTree
from typing import override

import requests
from loguru import logger
from pydantic import BaseModel

from digest.sources.base import BaseDataSource
from digest.sources.hansard.constants import BASE_URL, FILE_PREFIXES, HansardSourceType


class Debate(BaseModel):
    """Debate."""

    date: date
    source: HansardSourceType
    xml_string: str


class HansardDataSource(BaseDataSource[[date, HansardSourceType, bool], Debate]):
    """Hansard data source class.

    Agent to download parse Hansard reports extracted by TheyWorkForYou
    (https://www.theyworkforyou.com).
    """

    name: str = "hansard"

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
            debate = Debate(
                date=dt, source=source, xml_string=self._get_content(dt, source)
            )
            self._store_to_cache(cache_path, debate.xml_string)
        else:
            debate = Debate(
                date=dt,
                source=source,
                xml_string=str(self._read_from_cache(cache_path)),
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
        while not content_found and not failed:
            path = self._get_url_path(dt, source, ascii_lowercase[version_idx])
            response = requests.get(f"{BASE_URL}/{path}")
            response.raise_for_status()
            response_str = response.content.strip()
            root = ElementTree.fromstring(response_str)
            if root.attrib.get("latest") == "yes":
                content_found = True
            else:
                version_idx += 1
                if version_idx >= len(ascii_lowercase):
                    failed = True
        if failed:
            logger.warning(
                f"Latest version not found for {source} on {dt}. Returning latest version."
            )
        return response_str.decode("utf-8")


def get_hansard_data_source() -> HansardDataSource:
    return HansardDataSource()
