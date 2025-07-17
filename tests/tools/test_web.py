"""Tests for web scraping utilities."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from selenium.common.exceptions import TimeoutException, WebDriverException

from digest.tools.web import WebScraper, WebScraperError


@pytest.fixture
def mock_driver() -> Mock:
    """Create a mock Chrome driver."""
    driver = Mock()
    driver.get = Mock()
    driver.page_source = "<html><body>Test HTML content</body></html>"
    driver.quit = Mock()
    driver.execute_script = Mock()
    return driver


@pytest.fixture
def mock_webdriver_wait() -> Mock:
    """Create a mock WebDriverWait."""
    wait = Mock()
    wait.until = Mock()
    return wait


def test_webscraper_init() -> None:
    """Test WebScraper initialization with default parameters."""
    scraper = WebScraper()

    assert scraper.headless is True
    assert scraper.timeout == 30
    assert scraper.user_agent is None
    assert scraper._driver is None


def test_webscraper_init_custom_params() -> None:
    """Test WebScraper initialization with custom parameters."""
    scraper = WebScraper(headless=False, timeout=60, user_agent="Custom User Agent")

    assert scraper.headless is False
    assert scraper.timeout == 60
    assert scraper.user_agent == "Custom User Agent"
    assert scraper._driver is None


def test_get_html_success(monkeypatch: pytest.MonkeyPatch, mock_driver: Mock) -> None:
    """Test successful HTML retrieval from a URL."""

    # Mock undetected_chromedriver.Chrome
    def mock_chrome_init(*args: object, **kwargs: object) -> Mock:
        return mock_driver

    monkeypatch.setattr("digest.tools.web.uc.Chrome", mock_chrome_init)

    scraper = WebScraper()
    result = scraper.get_html("https://example.com")

    # Verify the driver was used correctly
    mock_driver.get.assert_called_once_with("https://example.com")
    mock_driver.execute_script.assert_called_once()
    mock_driver.quit.assert_called_once()

    # Verify the result
    assert result == "<html><body>Test HTML content</body></html>"


def test_get_html_with_wait_for_element(
    monkeypatch: pytest.MonkeyPatch, mock_driver: Mock, mock_webdriver_wait: Mock
) -> None:
    """Test HTML retrieval with wait for specific element."""

    # Mock undetected_chromedriver.Chrome
    def mock_chrome_init(*args: object, **kwargs: object) -> Mock:
        return mock_driver

    # Mock WebDriverWait
    def mock_wait_init(*args: object, **kwargs: object) -> Mock:
        return mock_webdriver_wait

    monkeypatch.setattr("digest.tools.web.uc.Chrome", mock_chrome_init)
    monkeypatch.setattr("digest.tools.web.WebDriverWait", mock_wait_init)

    scraper = WebScraper()
    result = scraper.get_html("https://example.com", wait_for_element=".content")

    # Verify the driver and wait were used correctly
    mock_driver.get.assert_called_once_with("https://example.com")
    mock_webdriver_wait.until.assert_called_once()
    mock_driver.quit.assert_called_once()

    # Verify the result
    assert result == "<html><body>Test HTML content</body></html>"


def test_get_html_invalid_url() -> None:
    """Test error handling for invalid URLs."""
    scraper = WebScraper()

    # Test empty string
    with pytest.raises(WebScraperError, match="URL must be a non-empty string"):
        scraper.get_html("")

    # Test None
    with pytest.raises(WebScraperError, match="URL must be a non-empty string"):
        scraper.get_html(None)  # type: ignore

    # Test non-string type
    with pytest.raises(WebScraperError, match="URL must be a non-empty string"):
        scraper.get_html(123)  # type: ignore


def test_get_html_webdriver_exception(
    monkeypatch: pytest.MonkeyPatch, mock_driver: Mock
) -> None:
    """Test error handling for WebDriver exceptions."""
    # Make the driver raise a WebDriverException
    mock_driver.get.side_effect = WebDriverException("Connection refused")

    def mock_chrome_init(*args: object, **kwargs: object) -> Mock:
        return mock_driver

    monkeypatch.setattr("digest.tools.web.uc.Chrome", mock_chrome_init)

    scraper = WebScraper()

    with pytest.raises(
        WebScraperError,
        match="Unexpected error while scraping https://example.com: Driver operation failed: Message: Connection refused",
    ):
        scraper.get_html("https://example.com")

    # Verify cleanup was attempted
    mock_driver.quit.assert_called_once()


def test_get_html_timeout_waiting_for_element(
    monkeypatch: pytest.MonkeyPatch, mock_driver: Mock, mock_webdriver_wait: Mock
) -> None:
    """Test timeout when waiting for specific element."""
    # Make WebDriverWait raise TimeoutException
    mock_webdriver_wait.until.side_effect = TimeoutException("Timeout")

    def mock_chrome_init(*args: object, **kwargs: object) -> Mock:
        return mock_driver

    def mock_wait_init(*args: object, **kwargs: object) -> Mock:
        return mock_webdriver_wait

    monkeypatch.setattr("digest.tools.web.uc.Chrome", mock_chrome_init)
    monkeypatch.setattr("digest.tools.web.WebDriverWait", mock_wait_init)

    scraper = WebScraper()
    # Should not raise exception, just log warning and continue
    result = scraper.get_html("https://example.com", wait_for_element=".missing")

    # Verify it still returns HTML despite timeout
    assert result == "<html><body>Test HTML content</body></html>"
    mock_driver.quit.assert_called_once()


def test_get_html_no_content(
    monkeypatch: pytest.MonkeyPatch, mock_driver: Mock
) -> None:
    """Test error handling when no HTML content is retrieved."""
    # Make page_source return empty content
    mock_driver.page_source = ""

    def mock_chrome_init(*args: object, **kwargs: object) -> Mock:
        return mock_driver

    monkeypatch.setattr("digest.tools.web.uc.Chrome", mock_chrome_init)

    scraper = WebScraper()

    with pytest.raises(
        WebScraperError, match="No HTML content retrieved from https://example.com"
    ):
        scraper.get_html("https://example.com")

    mock_driver.quit.assert_called_once()


def test_create_driver_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test error handling when driver creation fails."""

    def mock_chrome_init(*args: object, **kwargs: object) -> Mock:
        raise Exception("Chrome binary not found")

    monkeypatch.setattr("digest.tools.web.uc.Chrome", mock_chrome_init)

    scraper = WebScraper()

    with pytest.raises(
        WebScraperError,
        match="Driver operation failed: Failed to create Chrome driver: Chrome binary not found",
    ):
        scraper.get_html("https://example.com")


def test_context_manager_success(
    monkeypatch: pytest.MonkeyPatch, mock_driver: Mock
) -> None:
    """Test WebScraper as context manager with successful operation."""

    def mock_chrome_init(*args: object, **kwargs: object) -> Mock:
        return mock_driver

    monkeypatch.setattr("digest.tools.web.uc.Chrome", mock_chrome_init)

    with WebScraper() as scraper:
        assert isinstance(scraper, WebScraper)
        result = scraper.get_html("https://example.com")
        assert result == "<html><body>Test HTML content</body></html>"


def test_context_manager_cleanup_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test context manager cleanup when exception occurs."""
    mock_driver = Mock()
    mock_driver.quit = Mock()

    def mock_chrome_init(*args: object, **kwargs: object) -> Mock:
        return mock_driver

    monkeypatch.setattr("digest.tools.web.uc.Chrome", mock_chrome_init)

    scraper = WebScraper()
    scraper._driver = mock_driver  # Simulate having a driver

    # Test cleanup during context manager exit
    with scraper:
        pass  # Context manager should clean up on exit

    mock_driver.quit.assert_called_once()


def test_driver_quit_failure_logged(
    monkeypatch: pytest.MonkeyPatch, mock_driver: Mock
) -> None:
    """Test that driver quit failures are logged but don't raise exceptions."""
    # Make quit raise an exception
    mock_driver.quit.side_effect = Exception("Quit failed")

    def mock_chrome_init(*args: object, **kwargs: object) -> Mock:
        return mock_driver

    monkeypatch.setattr("digest.tools.web.uc.Chrome", mock_chrome_init)

    scraper = WebScraper()

    # Should complete successfully despite quit failure
    result = scraper.get_html("https://example.com")
    assert result == "<html><body>Test HTML content</body></html>"

    # Verify quit was attempted
    mock_driver.quit.assert_called_once()
