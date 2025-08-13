from asyncio import Runner
from datetime import date, datetime
from string import Template
from textwrap import dedent
from typing import Annotated
from pathlib import Path

import yaml
from loguru import logger
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from typer import Argument, Option, Typer

from digest.settings import openai_provider
from digest.sources.hansard.constants import Persona, HansardSourceType, PERSONA_PROMPTS
from digest.sources.hansard.main import get_hansard_data_source

cli = Typer(name="hansard")

SYSTEM_PROMPT_TEMPLATE = Template(
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

hansard_data_source = get_hansard_data_source()

model = OpenAIModel(
    "gpt-4.1-mini-2025-04-14",
    provider=openai_provider,
)
agent = Agent(model, deps_type=str)


@agent.system_prompt
def create_system_prompt(ctx: RunContext[str]) -> str:
    return SYSTEM_PROMPT_TEMPLATE.safe_substitute(persona=ctx.deps)


async def get_hansard_summary(
    dt: date, source: HansardSourceType = HansardSourceType.DEBATES
) -> dict[Persona, str]:
    debate = hansard_data_source.get(dt, source)
    summaries: dict[Persona, str] = {}
    for persona, prompt in PERSONA_PROMPTS.items():
        logger.info(f"Generating summary for persona: {persona.title()}")
        result = await agent.run(debate.xml_string, deps=prompt)
        logger.info(f"Summary for {persona.title()} persona:\n{result.output}")
        summaries[persona] = result.output
    return summaries


@cli.command()
def summarise(
    dt: Annotated[
        datetime, Argument(formats=["%Y-%m-%d"], help="Date of debate to summarise.")
    ],
    source: Annotated[
        HansardSourceType, Option(help="Source of debate to summarise.")
    ] = HansardSourceType.DEBATES,
    output_dir: Annotated[
        Path | None,
        Option(
            help="Path to which summaries will be written. No summary will be written if this is not provided",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ] = None,
) -> None:
    with Runner() as runner:
        try:
            result = runner.run(get_hansard_summary(dt.date(), source))
        except KeyboardInterrupt:
            logger.info("Summarisation cancelled by user")
    if output_dir:
        with (output_dir / f"{dt.date()}-{source.value}-summary.yaml").open("w") as f:
            yaml.dump(
                result,
                f,
                encoding="utf-8",
                allow_unicode=True,
                sort_keys=False,
                width=100,
                indent=2,
            )
