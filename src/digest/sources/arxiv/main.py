from datetime import date, datetime
from typing import override
from xml.etree import ElementTree

import requests
from loguru import logger
from pydantic import BaseModel
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from digest.sources.base import BaseDataSource

ARXIV_API_URL = "https://export.arxiv.org/api/query"

ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


class ArxivAuthor(BaseModel):
    """ArXiv article author."""

    name: str


class ArxivArticle(BaseModel):
    """ArXiv article metadata."""

    arxiv_id: str
    title: str
    summary: str
    authors: list[ArxivAuthor]
    categories: list[str]
    primary_category: str
    published: datetime
    updated: datetime
    pdf_url: str
    arxiv_url: str


class ArxivArticles(BaseModel):
    """Container for ArXiv articles."""

    articles: list[ArxivArticle]


class ArxivDataSource(BaseDataSource[[str, date, date], ArxivArticles]):
    """ArXiv data source class.

    Queries the ArXiv API for articles matching a search query within a date range.
    """

    name: str = "arxiv"

    @override
    def get(self, query: str, start_date: date, end_date: date) -> ArxivArticles:
        """Query ArXiv for articles matching the search criteria.

        Args:
            query: ArXiv search query string (e.g., "cat:cs.AI" or "all:transformer").
            start_date: Start date for filtering articles (inclusive).
            end_date: End date for filtering articles (inclusive).

        Returns:
            ArxivArticles object containing the list of matching articles.
        """
        full_query = self._build_query(query, start_date, end_date)
        response_text = self._fetch_arxiv(full_query)
        articles = self._parse_response(response_text)
        return ArxivArticles(articles=articles)

    def _build_query(self, query: str, start_date: date, end_date: date) -> str:
        """Build the full ArXiv query string with date range.

        Args:
            query: Base search query.
            start_date: Start date for filtering.
            end_date: End date for filtering.

        Returns:
            Full query string with date range filter.
        """
        start_str = start_date.strftime("%Y%m%d") + "0000"
        end_str = end_date.strftime("%Y%m%d") + "2359"
        date_filter = f"submittedDate:[{start_str} TO {end_str}]"
        return f"{query} AND {date_filter}"

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type((requests.exceptions.RequestException,)),
        reraise=True,
    )
    def _fetch_arxiv(self, query: str) -> str:
        """Fetch results from the ArXiv API with retry logic.

        Args:
            query: Full ArXiv query string.

        Returns:
            Raw XML response from the API.

        Raises:
            requests.exceptions.HTTPError: If the request fails after retries.
        """
        logger.info(f"Querying ArXiv API: {query}")
        params: dict[str, str | int] = {
            "search_query": query,
            "start": 0,
            "max_results": 1000,
        }
        response = requests.get(ARXIV_API_URL, params=params, timeout=30)
        response.raise_for_status()
        return response.text

    def _parse_response(self, xml_text: str) -> list[ArxivArticle]:
        """Parse ArXiv API XML response into ArxivArticle objects.

        Args:
            xml_text: Raw XML response from the ArXiv API.

        Returns:
            List of ArxivArticle objects parsed from the response.
        """
        root = ElementTree.fromstring(xml_text)
        articles: list[ArxivArticle] = []

        for entry in root.findall(f"{ATOM_NS}entry"):
            article = self._parse_entry(entry)
            if article is not None:
                articles.append(article)

        logger.info(f"Parsed {len(articles)} articles from ArXiv response")
        return articles

    def _parse_entry(self, entry: ElementTree.Element) -> ArxivArticle | None:
        """Parse a single entry element into an ArxivArticle.

        Args:
            entry: XML entry element from the ArXiv response.

        Returns:
            ArxivArticle object or None if parsing fails.
        """
        id_elem = entry.find(f"{ATOM_NS}id")
        title_elem = entry.find(f"{ATOM_NS}title")
        summary_elem = entry.find(f"{ATOM_NS}summary")
        published_elem = entry.find(f"{ATOM_NS}published")
        updated_elem = entry.find(f"{ATOM_NS}updated")
        primary_cat_elem = entry.find(f"{ARXIV_NS}primary_category")

        if (
            id_elem is None
            or id_elem.text is None
            or title_elem is None
            or title_elem.text is None
            or summary_elem is None
            or summary_elem.text is None
            or published_elem is None
            or published_elem.text is None
            or updated_elem is None
            or updated_elem.text is None
            or primary_cat_elem is None
        ):
            logger.warning("Skipping entry with missing required fields")
            return None

        arxiv_id = id_elem.text.split("/abs/")[-1]
        title = " ".join(title_elem.text.split())
        summary = " ".join(summary_elem.text.split())

        authors: list[ArxivAuthor] = []
        for author_elem in entry.findall(f"{ATOM_NS}author"):
            name_elem = author_elem.find(f"{ATOM_NS}name")
            if name_elem is not None and name_elem.text is not None:
                authors.append(ArxivAuthor(name=name_elem.text))

        categories: list[str] = []
        for cat_elem in entry.findall(f"{ATOM_NS}category"):
            term = cat_elem.get("term")
            if term is not None:
                categories.append(term)

        primary_category = primary_cat_elem.get("term", "")

        pdf_url = ""
        arxiv_url = ""
        for link_elem in entry.findall(f"{ATOM_NS}link"):
            link_type = link_elem.get("type", "")
            link_rel = link_elem.get("rel", "")
            link_href = link_elem.get("href", "")
            if link_type == "application/pdf":
                pdf_url = link_href
            elif link_rel == "alternate":
                arxiv_url = link_href

        published = datetime.fromisoformat(published_elem.text.replace("Z", "+00:00"))
        updated = datetime.fromisoformat(updated_elem.text.replace("Z", "+00:00"))

        return ArxivArticle(
            arxiv_id=arxiv_id,
            title=title,
            summary=summary,
            authors=authors,
            categories=categories,
            primary_category=primary_category,
            published=published,
            updated=updated,
            pdf_url=pdf_url,
            arxiv_url=arxiv_url,
        )


def get_arxiv_data_source() -> ArxivDataSource:
    """Get an ArXiv data source instance.

    Returns:
        ArxivDataSource instance.
    """
    return ArxivDataSource()
