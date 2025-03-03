from datetime import datetime, timedelta
from typing import List, Union, Optional
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
    authors: List[str]
    published: datetime
    updated: datetime
    primary_category: str
    categories: List[str]


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
        # Default the submission date range to previous day if not provided.
        if submitted_range_start is None or submitted_range_end is None:
            yesterday = datetime.utcnow() - timedelta(days=1)
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

        # Map the field to its query prefix.
        field_prefix = "ti:" if field == "title" else "abs:"

        # Ensure query is a list.
        queries = [query] if isinstance(query, str) else query
        # Build the query phrases, wrapping them in quotes to enforce phrase searching.
        phrase_queries = [f'{field_prefix}"{phrase}"' for phrase in queries]
        # If multiple phrases, join them with OR and wrap with parentheses.
        query_condition = (
            phrase_queries[0]
            if len(phrase_queries) == 1
            else "(" + " OR ".join(phrase_queries) + ")"
        )

        # Build category condition if provided.
        cat_condition = ""
        if category:
            cats = [category] if isinstance(category, str) else category
            if len(cats) == 1:
                cat_condition = f"cat:{cats[0]}"
            else:
                cat_condition = "(" + " OR ".join(f"cat:{cat}" for cat in cats) + ")"

        # Format the submitted range dates.
        start_str = submitted_range_start.strftime("%Y%m%d%H%M")
        end_str = submitted_range_end.strftime("%Y%m%d%H%M")
        date_condition = f"submittedDate:[{start_str} TO {end_str}]"

        # Combine all conditions with AND.
        conditions = [query_condition, date_condition]
        if cat_condition:
            conditions.insert(0, cat_condition)  # Put category filter first.

        search_query = " AND ".join(conditions)

        # Construct query parameters.
        params = {"search_query": search_query}

        # Encode the parameters using the safe characters as shown in the example.
        url = self.BASE_URL
        encoded_params = urlencode(params, safe=':+()"')
        response = requests.get(url, params=encoded_params)
        response.raise_for_status()

        # Parse the XML response.
        root = ET.fromstring(response.content)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }

        entries = []
        for element in root.findall("atom:entry", ns):
            entry_id = element.find("atom:id", ns).text
            title = element.find("atom:title", ns).text.strip()
            summary = element.find("atom:summary", ns).text.strip()
            published = datetime.fromisoformat(
                element.find("atom:published", ns).text.replace("Z", "+00:00")
            )
            updated = datetime.fromisoformat(
                element.find("atom:updated", ns).text.replace("Z", "+00:00")
            )
            authors = [
                author.find("atom:name", ns).text
                for author in element.findall("atom:author", ns)
            ]
            categories = [
                cat.attrib["term"] for cat in element.findall("atom:category", ns)
            ]
            primary = element.find("arxiv:primary_category", ns).attrib["term"]

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
