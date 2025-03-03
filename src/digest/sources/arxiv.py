from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests
import xml.etree.ElementTree as ET
from pydantic import BaseModel


class ArxivEntry(BaseModel):
    """ArXiv API result entry.

    Attributes:
        id (str): The ID/URL of the entry.
        title (str): The paper's title.
        summary (str): The paper's summary.
        authors (List[str]): A list of author names.
        published (datetime): The publication date.
        updated (datetime): The last updated date.
        primary_category (str): The primary category term.
        categories (List[str]): All categories associated with the paper.
    """

    id: str
    title: str
    summary: str
    authors: list[str]
    published: datetime
    updated: datetime
    primary_category: str
    categories: list[str]


class ArxivSearch:
    """Interface class for searching ArXiv.

    Provides a method to search ArXiv using various filters
    such as query phrases, field, category, and submission date range.
    """

    BASE_URL = "https://export.arxiv.org/api/query"

    def search(
        self,
        query: str | list[str],
        field: str = "abstract",
        category: str | list[str] | None = None,
        submitted_range_start: datetime | None = None,
        submitted_range_end: datetime | None = None,
    ) -> list[ArxivEntry]:
        """Search ArXiv and return search results as a list of ArxivEntry models.

        Args:
            query: A single phrase or a list of phrases to search for.
            field: The field to search on; either "title" or "abstract". Defaults to "abstract".
            category: Category or list of categories to filter on. If None, no category filtering is applied.
            submitted_range_start: Start datetime for the submittedDate filter. Defaults to the start of the previous day.
            submitted_range_end: End datetime for the submittedDate filter. Defaults to the end of the previous day.

        Returns:
            A list of ArxivEntry models representing search results.
        """
        submitted_range_start, submitted_range_end = self._default_date_range(
            submitted_range_start, submitted_range_end
        )
        query_condition = self._build_query_condition(query, field)
        cat_condition = self._build_category_condition(category)
        date_condition = self._build_date_condition(submitted_range_start, submitted_range_end)
        conditions = []
        if cat_condition:
            conditions.append(cat_condition)
        conditions.extend([query_condition, date_condition])
        search_query = self._build_search_query(conditions)
        params = {"search_query": search_query}
        encoded_params = urlencode(params, safe=':+()"')
        response = self._execute_request(encoded_params)
        return self._parse_response(response.content)
