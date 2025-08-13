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


class HansardDataSource(BaseDataSource[Debate]):
    """Hansard data source class.

    Agent to download parse Hansard reports extracted by TheyWorkForYou
    (https://www.theyworkforyou.com).
    """

    def __init__(self) -> None:
        """Initialize the Hansard data source."""

    @override
    def get(self, dt: date, source: HansardSourceType) -> Debate:
        """Extract Hansard report for a specific date.

        Args:
            dt: Date to extract Hansard report for.
            source: Source to extract Hansard report from.

        Returns:
            Debate object containing the extracted Hansard report.
        """
        return Debate(date=dt, source=source, xml_string=self._get_content(dt, source))

    def _get_path(self, dt: date, source: HansardSourceType, version: str = "a") -> str:
        """Get path for a specific date.

        Args:
            source: Source to get path for.
            dt: Date to get path for.

        Returns:
            URL path for the given date.
        """
        if version not in ascii_lowercase:
            raise ValueError("version must be a single lowercase letter")
        return f"{source}/{FILE_PREFIXES[source]}{dt.strftime('%Y-%m-%d')}{version}.xml"

    def _get_content(self, dt: date, source: HansardSourceType) -> str:
        """Get content for a specific source and date.

        Args:
            source: Source to get content for.
            dt: Date to get content for.

        Returns:
            String containing the raw XML content.
        """
        content_found = False
        failed = False
        version_idx = 0
        while not content_found and not failed:
            path = self._get_path(dt, source, ascii_lowercase[version_idx])
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
