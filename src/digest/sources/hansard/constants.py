from enum import StrEnum
from typing import Final

BASE_URL: Final = "https://hansard.parliament.uk"


class Chamber(StrEnum):
    """Enum for the chambers of parliament."""

    COMMONS = "commons"
    LORDS = "lords"
