from abc import ABC, abstractmethod

from pydantic import BaseModel
from digest.cache import DataCache, get_data_cache
from pathlib import Path
from loguru import logger


class BaseDataSource[**P, T: BaseModel](ABC):
    """Base data source class."""

    name: str

    def __init__(self, data_cache: DataCache | None = None) -> None:
        """Initialize the data source."""
        self._data_cache = data_cache or get_data_cache()

    @abstractmethod
    def get(self, *args: P.args, **kwargs: P.kwargs) -> T:
        """Get content from the data source.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Content from the data source as a Pydantic model.
        """
        raise NotImplementedError

    def _store_to_cache(self, path: str | Path, data: str | bytes) -> None:
        """Store data to the cache.

        Args:
            path: Path to store data to.
            data: Data to store.
        """
        logger.info(f"Storing data to cache: {path}")
        self._data_cache.write(path, data)

    def _read_from_cache(self, path: str | Path) -> str | bytes:
        """Read data from the cache.

        Args:
            path: Path to read data from.

        Returns:
            Data read from the cache.
        """
        logger.info(f"Reading data from cache: {path}")
        return self._data_cache.read(path)

    def _exists_in_cache(self, path: str | Path) -> bool:
        """Check if a path exists in the cache.

        Args:
            path: Path to check.

        Returns:
            True if the path exists, False otherwise.
        """
        return self._data_cache.exists(path)
