from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch


from digest.sources.arxiv.main import (
    ArxivArticle,
    ArxivArticles,
    ArxivAuthor,
    ArxivDataSource,
    get_arxiv_data_source,
)
from tests import TEST_DATA_DIR


def load_sample_xml() -> str:
    """Load sample ArXiv API response XML.

    Returns:
        str: Sample XML response.
    """
    xml_path = TEST_DATA_DIR / "arxiv_sample_response.xml"
    return xml_path.read_text(encoding="utf-8")


class TestArxivArticleModel:
    """Tests for ArxivArticle Pydantic model."""

    def test_arxiv_article_creation(self) -> None:
        """Test ArxivArticle can be created with valid data."""
        article = ArxivArticle(
            arxiv_id="2501.12345v1",
            title="Test Article",
            summary="This is a test summary.",
            authors=[ArxivAuthor(name="Test Author")],
            categories=["cs.AI", "cs.CL"],
            primary_category="cs.AI",
            published=datetime(2025, 1, 8, 18, 0, 0, tzinfo=timezone.utc),
            updated=datetime(2025, 1, 8, 18, 0, 0, tzinfo=timezone.utc),
            pdf_url="http://arxiv.org/pdf/2501.12345v1",
            arxiv_url="http://arxiv.org/abs/2501.12345v1",
        )
        assert article.arxiv_id == "2501.12345v1"
        assert article.title == "Test Article"
        assert len(article.authors) == 1
        assert article.authors[0].name == "Test Author"

    def test_arxiv_articles_container(self) -> None:
        """Test ArxivArticles container model."""
        article = ArxivArticle(
            arxiv_id="2501.12345v1",
            title="Test Article",
            summary="Summary",
            authors=[],
            categories=["cs.AI"],
            primary_category="cs.AI",
            published=datetime(2025, 1, 8, tzinfo=timezone.utc),
            updated=datetime(2025, 1, 8, tzinfo=timezone.utc),
            pdf_url="",
            arxiv_url="",
        )
        container = ArxivArticles(articles=[article])
        assert len(container.articles) == 1
        assert container.articles[0].arxiv_id == "2501.12345v1"


class TestArxivDataSource:
    """Tests for ArxivDataSource class."""

    def test_build_query(self) -> None:
        """Test query string building with date range."""
        source = ArxivDataSource()
        query = source._build_query(
            "cat:cs.AI",
            date(2025, 1, 1),
            date(2025, 1, 10),
        )
        assert "cat:cs.AI" in query
        assert "submittedDate:[202501010000 TO 202501102359]" in query
        assert " AND " in query

    def test_parse_response_extracts_articles(self) -> None:
        """Test parsing ArXiv API XML response."""
        source = ArxivDataSource()
        xml = load_sample_xml()
        articles = source._parse_response(xml)

        assert len(articles) == 2

        first = articles[0]
        assert first.arxiv_id == "2501.12345v1"
        assert first.title == "Advances in Large Language Model Reasoning"
        assert "comprehensive study" in first.summary
        assert len(first.authors) == 2
        assert first.authors[0].name == "Alice Smith"
        assert first.authors[1].name == "Bob Jones"
        assert first.primary_category == "cs.AI"
        assert "cs.AI" in first.categories
        assert "cs.CL" in first.categories
        assert first.pdf_url == "http://arxiv.org/pdf/2501.12345v1"
        assert first.arxiv_url == "http://arxiv.org/abs/2501.12345v1"

        second = articles[1]
        assert second.arxiv_id == "2501.67890v2"
        assert second.title == "Neural Architecture Search for Efficient Transformers"
        assert len(second.authors) == 1
        assert second.authors[0].name == "Carol Williams"
        assert second.primary_category == "cs.LG"
        assert len(second.categories) == 3

    def test_parse_response_handles_empty_feed(self) -> None:
        """Test parsing handles empty feed gracefully."""
        source = ArxivDataSource()
        empty_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <title>ArXiv Query</title>
        </feed>
        """
        articles = source._parse_response(empty_xml)
        assert articles == []

    def test_get_returns_arxiv_articles(self) -> None:
        """Test get method returns ArxivArticles object."""
        source = ArxivDataSource()
        xml = load_sample_xml()

        with patch.object(source, "_fetch_arxiv", return_value=xml):
            result = source.get("cat:cs.AI", date(2025, 1, 1), date(2025, 1, 10))

        assert isinstance(result, ArxivArticles)
        assert len(result.articles) == 2
        assert result.articles[0].arxiv_id == "2501.12345v1"

    def test_fetch_arxiv_uses_correct_params(self) -> None:
        """Test that _fetch_arxiv calls the API with correct parameters."""
        source = ArxivDataSource()
        mock_response = MagicMock()
        mock_response.text = load_sample_xml()
        mock_response.raise_for_status = MagicMock()

        with patch("digest.sources.arxiv.main.requests.get") as mock_get:
            mock_get.return_value = mock_response
            result = source._fetch_arxiv(
                "cat:cs.AI AND submittedDate:[202501010000 TO 202501102359]"
            )

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args.args[0] == "https://export.arxiv.org/api/query"
        params = call_args.kwargs["params"]
        assert "cat:cs.AI" in params["search_query"]
        assert params["start"] == 0
        assert params["max_results"] == 1000
        assert result == mock_response.text


class TestFactoryFunction:
    """Tests for factory function."""

    def test_get_arxiv_data_source_returns_instance(self) -> None:
        """Test factory function returns ArxivDataSource instance."""
        source = get_arxiv_data_source()
        assert isinstance(source, ArxivDataSource)
        assert source.name == "arxiv"
