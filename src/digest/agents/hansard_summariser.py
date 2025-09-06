from asyncio import Runner
from datetime import date, datetime
from string import Template
from textwrap import dedent
from typing import Annotated

from loguru import logger
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from typer import Argument, Option, Typer

from digest.settings import openai_provider
from digest.site import create_post, format_post, get_all_tags
from digest.sources.hansard.constants import Persona, HansardSourceType, PERSONA_PROMPTS
from digest.sources.hansard.main import get_hansard_data_source

cli = Typer(name="hansard")

SUMMARY_SYSTEM_PROMPT_TEMPLATE = Template(
    dedent(
        """
        <persona>
        ${persona}
        </persona>
        <task>
        Write an executive summary of the parliamentary debate provided by the user.
        Write in full prose, not bullet points.
        Use neutral, report-style language. Do not express approval, disapproval, or speculation.
        DO NOT include commentary, jokes, persuasion, or rhetorical questions.
        Use direct quotes where relevant.
        Always cite the paragraph ID(s) when giving direct quotes.
        A paragraph ID is given by the pid attribute of each <p>...</p> block.
        Just quote the paragraph ID in the citation e.g. (b676.1/1) not (pid=b676.1/1).
        </task>
        """
    )
)
SUMMARY_TEMPLATE = Template(
    dedent(
        """
        ## From the Perspective of the ${persona}

        ${summary}
        """
    )
)
TAG_SYSTEM_PROMPT_TEMPLATE = Template(
    dedent(
        """
        <existing_tags>
        ${existing_tags}
        </existing_tags>
        <task>
        Generate 1-5 tags for the content provided by the user.
        A tag is a short lowercase word (no spaces) that represents a topic discussed in the content.
        Examples: healthcare, economy, environment.
        </task>
        """
    )
)

hansard_data_source = get_hansard_data_source()

model = OpenAIModel(
    "gpt-5-mini-2025-08-07",
    provider=openai_provider,
)
summary_agent = Agent(model, deps_type=str)
tag_agent = Agent(model, deps_type=set[str], output_type=list[str])


@summary_agent.system_prompt
def create_system_prompt(ctx: RunContext[str]) -> str:
    return SUMMARY_SYSTEM_PROMPT_TEMPLATE.safe_substitute(persona=ctx.deps)


@tag_agent.system_prompt
def create_tag_system_prompt(ctx: RunContext[set[str]]) -> str:
    existing_tags = "\n".join([f"- {tag}" for tag in ctx.deps])
    return TAG_SYSTEM_PROMPT_TEMPLATE.safe_substitute(existing_tags=existing_tags)


async def get_hansard_summary(
    dt: date, source: HansardSourceType = HansardSourceType.DEBATES
) -> dict[Persona, str]:
    debate = hansard_data_source.get(dt, source)
    summaries: dict[Persona, str] = {}
    for persona, prompt in PERSONA_PROMPTS.items():
        logger.info(f"Generating summary for persona: {persona.title()}")
        result = await summary_agent.run(debate.xml_string, deps=prompt)
        logger.info(f"Summary for {persona.title()} persona:\n{result.output}")
        summaries[persona] = result.output
    return summaries


async def get_tags(summary: str, existing_tags: set[str]) -> list[str]:
    result = await tag_agent.run(summary, deps=existing_tags)
    tags = [tag.lower() for tag in result.output]
    logger.info(f"Tags: {', '.join(tags)}")
    return tags


def format_hansard_summaries(
    summaries: dict[Persona, str], source: HansardSourceType
) -> str:
    """Format generated summaries as a markdown string.

    Args:
        summaries: Dictionary of summaries, with Persona as key and summary as value.
        source: Source of the debate.

    Returns:
        Formatted summaries as a markdown string.
    """
    return "\n\n".join(
        SUMMARY_TEMPLATE.safe_substitute(
            persona=persona.value.title(), summary=summary
        ).strip()
        for persona, summary in summaries.items()
    )


@cli.command()
def summarise(
    dt: Annotated[
        datetime, Argument(formats=["%Y-%m-%d"], help="Date of debate to summarise.")
    ],
    source: Annotated[
        HansardSourceType, Option(help="Source of debate to summarise.")
    ] = HansardSourceType.DEBATES,
    publish: Annotated[bool, Option(help="Publish summaries as a post.")] = False,
) -> None:
    with Runner() as runner:
        try:
            result = runner.run(get_hansard_summary(dt.date(), source))
        except KeyboardInterrupt:
            logger.info("Summarisation cancelled by user")
    if publish:
        summary = format_hansard_summaries(result, source)
        existing_tags = get_all_tags("hansard")
        with Runner() as runner:
            try:
                tags = runner.run(get_tags(summary, existing_tags))
            except KeyboardInterrupt:
                logger.info("Tag generation cancelled by user")
        post_content = format_post(
            summary,
            dt.date(),
            f"{source.value.title()} Summary for {dt.strftime('%B %d, %Y')}",
            tags=tags,
        )
        create_post(
            site="hansard",
            content=post_content,
            post_path=f"{dt.date()}-{source.value}-summary.md",
            section=source.value,
        )
