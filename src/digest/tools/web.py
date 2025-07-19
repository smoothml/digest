"""Web scraping utilities using Selenium with undetected-chromedriver."""

from __future__ import annotations

import random
import time
from contextlib import contextmanager
from typing import Generator

import undetected_chromedriver as uc
from loguru import logger
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class WebScraperError(Exception):
    """Base exception for WebScraper errors."""


class WebScraper:
    """Web scraper using Selenium with undetected-chromedriver.

    This class provides methods to scrape web content using a Chrome browser
    instance that is less likely to be detected by anti-bot measures.
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout: int = 30,
        user_agent: str | None = None,
        wait_for_cloudflare: bool = True,
        max_wait_time: int = 30,
    ) -> None:
        """Initialize the WebScraper.

        Args:
            headless: Whether to run Chrome in headless mode.
            timeout: Default timeout for page loads in seconds.
            user_agent: Custom user agent string. If None, uses default.
            wait_for_cloudflare: Whether to wait for Cloudflare challenges to complete.
            max_wait_time: Maximum time to wait for Cloudflare challenges in seconds.
        """
        self.headless = headless
        self.timeout = timeout
        self.user_agent = user_agent or self._get_random_user_agent()
        self.wait_for_cloudflare = wait_for_cloudflare
        self.max_wait_time = max_wait_time
        self._driver: uc.Chrome | None = None

    def _create_driver(self) -> uc.Chrome:
        """Create and configure Chrome driver.

        Returns:
            Configured Chrome driver instance.

        Raises:
            WebScraperError: If driver creation fails.
        """
        try:
            options = Options()

            if self.headless:
                options.add_argument("--headless=new")

            # Enhanced anti-detection options
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-plugins")
            options.add_argument("--disable-images")
            options.add_argument("--disable-web-security")
            options.add_argument("--disable-features=VizDisplayCompositor")
            options.add_argument("--disable-ipc-flooding-protection")
            options.add_argument("--no-first-run")
            options.add_argument("--no-service-autorun")
            options.add_argument("--password-store=basic")
            options.add_argument("--use-mock-keychain")
            options.add_argument("--disable-background-timer-throttling")
            options.add_argument("--disable-renderer-backgrounding")
            options.add_argument("--disable-backgrounding-occluded-windows")

            # Set user agent
            options.add_argument(f"--user-agent={self.user_agent}")

            # Set window size to avoid headless detection
            options.add_argument("--window-size=1920,1080")

            # Create driver with enhanced options
            driver = uc.Chrome(
                options=options,
                version_main=None,  # Auto-detect Chrome version
                use_subprocess=False,
            )

            # Execute script to remove webdriver property
            driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            return driver

        except Exception as e:
            raise WebScraperError(f"Failed to create Chrome driver: {e}") from e

    def _get_random_user_agent(self) -> str:
        """Get a random realistic user agent string.

        Returns:
            Random user agent string.
        """
        user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        ]
        return random.choice(user_agents)

    def _is_cloudflare_challenge(self, driver: uc.Chrome) -> bool:
        """Check if the current page is a Cloudflare challenge.

        Args:
            driver: Chrome driver instance.

        Returns:
            True if Cloudflare challenge is detected, False otherwise.
        """
        try:
            # Check for common Cloudflare challenge indicators
            cloudflare_indicators = [
                "Just a moment...",
                "Checking your browser before accessing",
                "This process is automatic",
                "Please allow up to 5 seconds",
                "DDoS protection by Cloudflare",
                "cf-browser-verification",
                "cf-challenge-running",
            ]

            page_source = driver.page_source.lower()
            page_title = driver.title.lower()

            for indicator in cloudflare_indicators:
                if indicator.lower() in page_source or indicator.lower() in page_title:
                    return True

            # Check for Cloudflare challenge elements
            try:
                challenge_elements = driver.find_elements(
                    By.CSS_SELECTOR,
                    '[id*="cf-"], [class*="cf-"], [id*="challenge"], [class*="challenge"]',
                )
                if challenge_elements:
                    return True
            except Exception:
                pass

            return False
        except Exception:
            return False

    def _handle_cloudflare_challenge(self, driver: uc.Chrome, url: str) -> None:
        """Handle Cloudflare challenge by waiting for it to complete.

        Args:
            driver: Chrome driver instance.
            url: The URL being accessed.

        Raises:
            WebScraperError: If challenge cannot be completed within timeout.
        """
        logger.info(f"Checking for Cloudflare challenge on {url}")

        if not self._is_cloudflare_challenge(driver):
            logger.debug("No Cloudflare challenge detected")
            return

        logger.info(
            f"Cloudflare challenge detected on {url}, waiting for completion..."
        )

        start_time = time.time()
        while time.time() - start_time < self.max_wait_time:
            # Wait a bit for challenge to process
            time.sleep(2)

            # Check if challenge is still present
            if not self._is_cloudflare_challenge(driver):
                logger.info(f"Cloudflare challenge completed for {url}")
                return

            # Add some randomness to appear more human-like
            time.sleep(random.uniform(1, 3))

            # Try to interact with the page slightly to appear more human
            try:
                driver.execute_script("window.scrollTo(0, 100);")
                time.sleep(random.uniform(0.5, 1.5))
                driver.execute_script("window.scrollTo(0, 0);")
            except Exception:
                pass

        # If we get here, the challenge didn't complete in time
        logger.warning(
            f"Cloudflare challenge timeout after {self.max_wait_time}s on {url}"
        )
        raise WebScraperError(
            f"Cloudflare challenge timeout on {url}. "
            f"Challenge did not complete within {self.max_wait_time} seconds."
        )

    @contextmanager
    def _get_driver(self) -> Generator[uc.Chrome, None, None]:
        """Context manager for Chrome driver.

        Yields:
            Chrome driver instance.

        Raises:
            WebScraperError: If driver operations fail.
        """
        driver = None
        try:
            driver = self._create_driver()
            yield driver
        except Exception as e:
            raise WebScraperError(f"Driver operation failed: {e}") from e
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    logger.warning(f"Failed to quit driver cleanly: {e}")

    def get_html(self, url: str, *, wait_for_element: str | None = None) -> str:
        """Get HTML content from a URL.

        Args:
            url: The URL to scrape.
            wait_for_element: Optional CSS selector to wait for before extracting HTML.

        Returns:
            The HTML content as a string.

        Raises:
            WebScraperError: If scraping fails.
        """
        if not url or not isinstance(url, str):
            raise WebScraperError("URL must be a non-empty string")

        logger.info(f"Scraping HTML from: {url}")

        try:
            with self._get_driver() as driver:
                # Navigate to the URL
                driver.get(url)

                # Handle Cloudflare challenges if enabled
                if self.wait_for_cloudflare:
                    self._handle_cloudflare_challenge(driver, url)

                # Wait for specific element if requested
                if wait_for_element:
                    try:
                        WebDriverWait(driver, self.timeout).until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, wait_for_element)
                            )
                        )
                        logger.debug(f"Found element: {wait_for_element}")
                    except TimeoutException:
                        logger.warning(
                            f"Timeout waiting for element '{wait_for_element}' on {url}"
                        )
                else:
                    # Give page time to load JavaScript content
                    time.sleep(2)

                # Get the page source
                html: str = driver.page_source

                if not html:
                    raise WebScraperError(f"No HTML content retrieved from {url}")

                # Check if we still have a Cloudflare challenge page
                if self._is_cloudflare_challenge(driver):
                    logger.warning(f"Cloudflare challenge still present on {url}")
                    raise WebScraperError(
                        f"Unable to bypass Cloudflare challenge on {url}. "
                        "The site may require manual verification or more advanced bypass techniques."
                    )

                logger.info(f"Successfully scraped {len(html)} characters from {url}")
                return html

        except WebDriverException as e:
            raise WebScraperError(f"WebDriver error while scraping {url}: {e}") from e
        except Exception as e:
            raise WebScraperError(f"Unexpected error while scraping {url}: {e}") from e

    def __enter__(self) -> WebScraper:
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Exit context manager."""
        if self._driver:
            try:
                self._driver.quit()
            except Exception as e:
                logger.warning(f"Failed to quit driver in context manager: {e}")
