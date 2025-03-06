from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests
import xml.etree.ElementTree as ET
from pydantic import BaseModel
from enum import StrEnum

class ArxivSearchField(StrEnum):
    """Enumeration of valid fields for Arxiv searches."""
    ABSTRACT = "abstract"
    TITLE = "title"


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
        field: ArxivSearchField = ArxivSearchField.ABSTRACT,
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
        date_condition = self._build_date_condition(
            submitted_range_start, submitted_range_end
        )
        conditions = []
        if cat_condition:
            conditions.append(cat_condition)
        conditions.extend([query_condition, date_condition])
        search_query = self._build_search_query(conditions)
        params = {"search_query": search_query}
        encoded_params = urlencode(params, safe=':+()"')
        response = self._execute_request(encoded_params)
        return self._parse_response(response.content)

    @staticmethod
    def _default_date_range(
        submitted_range_start: datetime | None, submitted_range_end: datetime | None
    ) -> tuple[datetime, datetime]:
        """
        Set default submitted date range if not provided.

        If either submitted_range_start or submitted_range_end is None, defaults to the start
        and end of the previous day in UTC.

        Args:
            submitted_range_start: Start datetime for filtering.
            submitted_range_end: End datetime for filtering.

        Returns:
            A tuple (start_datetime, end_datetime).
        """
        if submitted_range_start is None or submitted_range_end is None:
            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            submitted_range_start = datetime(
                year=yesterday.year,
                month=yesterday.month,
                day=yesterday.day,
                hour=0,
                minute=0,
            )
            submitted_range_end = datetime(
                year=yesterday.year,
                month=yesterday.month,
                day=yesterday.day,
                hour=23,
                minute=59,
            )
        return submitted_range_start, submitted_range_end

    @staticmethod
    def _build_query_condition(query: str | list[str], field: ArxivSearchField) -> str:
        """
        Construct the query fragment for the given query or queries and field.

        Args:
            query: A single phrase or a list of phrases to search for.
            field: The field to search on; expected to be either "title" or "abstract".

        Returns:
            A query fragment string.
        """
        field_prefix = "ti:" if field == ArxivSearchField.TITLE else "abs:"
        queries = [query] if isinstance(query, str) else query
        phrase_queries = [f'{field_prefix}"{phrase}"' for phrase in queries]
        return (
            phrase_queries[0]
            if len(phrase_queries) == 1
            else "(" + " OR ".join(phrase_queries) + ")"
        )

    @staticmethod
    def _build_category_condition(category: str | list[str] | None) -> str:
        """
        Build the category filter fragment for the API query.

        Args:
            category: A category string, a list of category strings, or None.

        Returns:
            A category condition string for the API query, or an empty string if no category is provided.
        """
        if not category:
            return ""
        cats = [category] if isinstance(category, str) else category
        if len(cats) == 1:
            return f"cat:{cats[0]}"
        return "(" + " OR ".join(f"cat:{cat}" for cat in cats) + ")"

    @staticmethod
    def _build_date_condition(start: datetime, end: datetime) -> str:
        """
        Construct the date condition fragment for the API query.

        Args:
            start: The start datetime.
            end: The end datetime.

        Returns:
            A string representing the date range filter.
        """
        start_str = start.strftime("%Y%m%d%H%M")
        end_str = end.strftime("%Y%m%d%H%M")
        return f"submittedDate:[{start_str} TO {end_str}]"

    @staticmethod
    def _build_search_query(conditions: list[str]) -> str:
        """
        Combine individual query fragments using the 'AND' operator.

        Args:
            conditions: A list of query condition strings.

        Returns:
            A single combined query string.
        """
        return " AND ".join(conditions)

    def _execute_request(self, encoded_params: str) -> requests.Response:
        """
        Execute the GET request to the ArXiv API with the provided encoded parameters.

        Args:
            encoded_params: The URL-encoded query parameters as a string.

        Returns:
            The Response object from the HTTP GET call.

        Raises:
            requests.HTTPError: If the HTTP request returns a non-200 status code.
        """
        response = requests.get(self.BASE_URL, params=encoded_params)
        response.raise_for_status()
        return response

    @staticmethod
    def _get_element_text(element: ET.Element | None) -> str:
        """
        Extract text from an XML element.

        Args:
            element: The XML element from which to extract text.

        Returns:
            The text content of the element.

        Raises:
            ValueError: If the element is None or has no text.
        """
        if element is None or element.text is None:
            raise ValueError("Missing expected element text")
        return element.text

    @staticmethod
    def _parse_response(content: bytes) -> list[ArxivEntry]:
        """
        Parse the API XML response into a list of ArxivEntry models.

        Args:
            content: The XML response as bytes.

        Returns:
            A list of ArxivEntry models extracted from the XML content.
        """
        root = ET.fromstring(content)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        entries = []
        for element in root.findall("atom:entry", ns):
            entry_id = ArxivSearch._get_element_text(element.find("atom:id", ns))
            title = ArxivSearch._get_element_text(
                element.find("atom:title", ns)
            ).strip()
            summary = ArxivSearch._get_element_text(
                element.find("atom:summary", ns)
            ).strip()
            published = datetime.fromisoformat(
                ArxivSearch._get_element_text(
                    element.find("atom:published", ns)
                ).replace("Z", "+00:00")
            )
            updated = datetime.fromisoformat(
                ArxivSearch._get_element_text(element.find("atom:updated", ns)).replace(
                    "Z", "+00:00"
                )
            )
            authors = [
                ArxivSearch._get_element_text(author.find("atom:name", ns))
                for author in element.findall("atom:author", ns)
            ]
            categories = [
                cat.attrib["term"] for cat in element.findall("atom:category", ns)
            ]
            primary_elem = element.find("arxiv:primary_category", ns)
            if primary_elem is None or "term" not in primary_elem.attrib:
                raise ValueError("Missing primary category")
            primary = primary_elem.attrib["term"]

            entries.append(
                ArxivEntry(
                    id=entry_id,
                    title=title,
                    summary=summary,
                    authors=authors,
                    published=published,
                    updated=updated,
                    primary_category=primary,
                    categories=categories,
                )
            )
        return entries
