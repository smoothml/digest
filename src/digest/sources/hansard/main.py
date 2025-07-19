import asyncio
from datetime import date
import re
from string import Template
from textwrap import dedent

import requests
from loguru import logger
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.settings import ModelSettings

from digest.tools.web import WebScraper
from digest.sources.hansard.constants import BASE_URL, Chamber
from digest.settings import openai_provider

PROMPT_TEMPLATE = Template(
    dedent(
        """
        <html_content>
        ${html_content}
        </html_content>
        <task>
        From the HTML content above, extract all `href` values starting with ${prefix}.
        </task>
        """
    )
)


class URLList(BaseModel):
    """List of URLs."""

    urls: list[str]


class Debate(BaseModel):
    """Debate."""

    name: str
    uid: str
    text: str | None = None


class HansardExtractionAgent:
    """Hansard data extraction agent."""

    def __init__(self) -> None:
        """Initialize the Hansard agent."""
        self._scraper = WebScraper()
        self._url_extractor_agent = Agent(
            model=OpenAIModel("gpt-4.1-2025-04-14", provider=openai_provider),
            name="URL Extractor",
            model_settings=ModelSettings(temperature=0.0),
            system_prompt="You are an expert at extracting URLs from HTML content.",
        )

    async def extract_day(self, chamber: Chamber, date: date) -> list[Debate]:
        """Extract Hansard report for a specific date."""
        path = f"/{chamber.value}/{date.strftime('%Y-%m-%d')}"
        prefix = f"{path}/debates"
        start_page_html = self._scraper.get_html(f"{BASE_URL}{path}")
        response = await self._url_extractor_agent.run(
            PROMPT_TEMPLATE.safe_substitute(
                html_content=start_page_html, prefix=prefix
            ),
            output_type=URLList,
        )
        url_list = response.output
        debates = self._extract_debate_details(url_list, prefix)
        return debates

    def _extract_debate_details(self, url_list: URLList, prefix: str) -> list[Debate]:
        """Extract debate details from URL paths."""
        pattern = re.compile(rf"(?<={prefix}/)([\w-]+)/([\w%]+)")
        debates = []
        for url in url_list.urls:
            debate_match = pattern.search(url)
            if debate_match:
                debate = Debate(name=debate_match.group(2), uid=debate_match.group(1))
                debate = self._get_debate_text(debate)
                if debate:
                    debates.append(debate)
        return debates

    def _get_debate_text(self, debate: Debate) -> Debate | None:
        """Get the text of a debate."""
        try:
            response = requests.get(
                f"{BASE_URL}/debates/GetDebateAsText/{debate.uid}",
                headers={
                    "Referer": f"{BASE_URL}",
                    "User-Agent": self._scraper.user_agent,
                },
            )
            response.raise_for_status()
            debate.text = response.text
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to get debate text: {e}")
            return None
        return debate


if __name__ == "__main__":
    hansard_extraction_agent = HansardExtractionAgent()
    print(asyncio.run(hansard_extraction_agent.extract_day(Chamber.COMMONS, date(2025, 7, 17))))
