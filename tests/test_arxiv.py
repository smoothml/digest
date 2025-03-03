from xml.etree import ElementTree
from datetime import datetime, timedelta, timezone
import pytest
from digest.sources.arxiv import ArxivSearch
import requests


# Dummy response class for mocking requests.get responses.
class DummyResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code != 200:
            raise requests.HTTPError(f"Status code: {self.status_code}")


@pytest.fixture
def arxiv_search():
    return ArxivSearch()


def dummy_xml_response() -> bytes:
    return b"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
       <entry>
         <id>http://arxiv.org/abs/1234.5678v1</id>
         <updated>2022-01-02T00:00:00Z</updated>
         <published>2022-01-01T00:00:00Z</published>
         <title>Test Title</title>
         <summary>Test Summary</summary>
         <author><name>Author One</name></author>
         <author><name>Author Two</name></author>
         <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
         <category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
       </entry>
    </feed>
    """


def test_default_date_range(arxiv_search: ArxivSearch) -> None:
    start, end = arxiv_search._default_date_range(None, None)
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    expected_start = datetime(
        year=yesterday.year, month=yesterday.month, day=yesterday.day, hour=0, minute=0
    )
    expected_end = datetime(
        year=yesterday.year,
        month=yesterday.month,
        day=yesterday.day,
        hour=23,
        minute=59,
    )
    assert start == expected_start
    assert end == expected_end


def test_build_query_condition(arxiv_search: ArxivSearch) -> None:
    single = arxiv_search._build_query_condition("test", "abstract")
    assert single == 'abs:"test"'
    multiple = arxiv_search._build_query_condition(["foo", "bar"], "title")
    assert multiple == '(ti:"foo" OR ti:"bar")'


def test_build_category_condition(arxiv_search: ArxivSearch) -> None:
    assert arxiv_search._build_category_condition(None) == ""
    assert arxiv_search._build_category_condition("cs.AI") == "cat:cs.AI"
    multiple_cat = arxiv_search._build_category_condition(["cs.AI", "cs.CL"])
    expected = "(cat:cs.AI OR cat:cs.CL)"
    assert multiple_cat == expected


def test_build_date_condition(arxiv_search: ArxivSearch) -> None:
    start = datetime(2022, 1, 1, 0, 0)
    end = datetime(2022, 1, 1, 23, 59)
    condition = arxiv_search._build_date_condition(start, end)
    assert condition == "submittedDate:[202201010000 TO 202201012359]"


def test_build_search_query(arxiv_search: ArxivSearch) -> None:
    conditions = [
        "cat:cs.AI",
        'abs:"test"',
        "submittedDate:[202201010000 TO 202201012359]",
    ]
    query = arxiv_search._build_search_query(conditions)
    assert (
        query
        == 'cat:cs.AI AND abs:"test" AND submittedDate:[202201010000 TO 202201012359]'
    )


def test_parse_response(arxiv_search: ArxivSearch) -> None:
    entries = arxiv_search._parse_response(dummy_xml_response())
    assert len(entries) == 1
    entry = entries[0]
    assert entry.id == "http://arxiv.org/abs/1234.5678v1"
    assert entry.title == "Test Title"
    assert entry.summary == "Test Summary"
    assert entry.authors == ["Author One", "Author Two"]
    assert entry.primary_category == "cs.AI"
    assert "cs.AI" in entry.categories


def test_execute_request(
    monkeypatch: pytest.MonkeyPatch, arxiv_search: ArxivSearch
) -> None:
    # Define a fake GET that returns our dummy XML response.
    def fake_get(url: str, params: str) -> DummyResponse:
        return DummyResponse(dummy_xml_response(), 200)

    monkeypatch.setattr(requests, "get", fake_get)
    encoded_params = "dummy"
    response = arxiv_search._execute_request(encoded_params)
    assert response.status_code == 200
    root = ElementTree.fromstring(response.content)
    # Check that an <entry> exists in the XML.
    assert root.find(".//{http://www.w3.org/2005/Atom}entry") is not None
