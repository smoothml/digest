from enum import StrEnum, auto
from typing import Final

BASE_URL: Final = "https://www.theyworkforyou.com/pwdata/scrapedxml"


class HansardSourceType(StrEnum):
    """Enum of Hansard data sources."""

    DEBATES = auto()


FILE_PREFIXES: Final = {
    HansardSourceType.DEBATES: "debates",
}
