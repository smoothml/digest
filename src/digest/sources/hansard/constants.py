from enum import StrEnum
from typing import Final

BASE_URL: Final = "https://www.theyworkforyou.com/pwdata/scrapedxml"


class HansardSourceType(StrEnum):
    """Enum of Hansard data sources."""

    COMMONS = "debates"  # Commons debates
    LORDS = "lordspages"  # Lords debates
    WESTMINSTER_HALL = "westminhall"  # Westminster Hall debates


class HansardSourceName(StrEnum):
    """Enum of Hansard data source names."""

    COMMONS = "commons"
    LORDS = "lords"
    WESTMINSTER_HALL = "westminster_hall"


FILE_PREFIXES: Final = {
    HansardSourceType.COMMONS: "debates",
    HansardSourceType.LORDS: "daylord",
    HansardSourceType.WESTMINSTER_HALL: "westminster",
}

SOURCE_TYPE_TO_NAME_MAP: Final = {
    HansardSourceType.COMMONS: HansardSourceName.COMMONS,
    HansardSourceType.LORDS: HansardSourceName.LORDS,
    HansardSourceType.WESTMINSTER_HALL: HansardSourceName.WESTMINSTER_HALL,
}

SOURCE_NAME_TO_TYPE_MAP: Final = {v: k for k, v in SOURCE_TYPE_TO_NAME_MAP.items()}
