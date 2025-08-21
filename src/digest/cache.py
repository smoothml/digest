from digest.settings import application_settings
import fsspec
from pathlib import Path


class DataCache:
    """Data cache class."""

    def __init__(self, url: str | None = None) -> None:
        """Initialize the data cache.

        Args:
            url: Base URL for the data cache.
        """
        self._url = (url or application_settings.data_cache_url).rstrip("/")

    def read(self, path: str | Path) -> str | bytes:
        """Read data from the data cache.

        Args:
            path: Path to read data from.

        Returns:
            Data read from the data cache.
        """
        mode = "r" if isinstance(path, str) else "rb"
        full_url = self._get_full_url(path)
        with fsspec.open(full_url, mode) as f:
            data: str | bytes = f.read()
        return data

    def write(self, path: str | Path, data: str | bytes) -> None:
        """Write data to the data cache.

        Args:
            path: Path to write data to.
            data: Data to write.
        """
        mode = "w" if isinstance(data, str) else "wb"
        full_url = self._get_full_url(path)
        with fsspec.open(full_url, mode) as f:
            f.write(data)

    def exists(self, path: str | Path) -> bool:
        """Check if a path exists in the data cache.

        Args:
            path: Path to check.

        Returns:
            True if the path exists, False otherwise.
        """
        full_url = self._get_full_url(path)
        protocol, path = full_url.split("://")
        exists: bool = fsspec.filesystem(protocol).exists(path)
        return exists

    def _get_full_url(self, path: str | Path) -> str:
        """Get the full URL for a path.

        Args:
            path: Path to get full URL for.

        Returns:
            Full URL for the given path.
        """
        path = str(path) if isinstance(path, Path) else path
        return self._url + "/" + path


def get_data_cache() -> DataCache:
    """Get data cache object.

    Returns:
        DataCache object.
    """
    return DataCache()
