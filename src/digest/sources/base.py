from abc import ABC, abstractmethod

from pydantic import BaseModel


class BaseDataSource[T: BaseModel](ABC):
    """Base data source class."""

    @abstractmethod
    def get(self) -> T:
        """Get content from the data source.

        Returns:
            Content from the data source as a Pydantic model.
        """
        raise NotImplementedError
