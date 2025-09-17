from asyncio import Runner
from datetime import datetime
from typing import Annotated

from loguru import logger
from typer import Argument, Option, Typer

from digest.sources.hansard.constants import HansardSourceType
from digest.agents.hansard_summariser.agent import get_hansard_summary, publish_summary

cli = Typer(name="hansard")


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
            summary = runner.run(get_hansard_summary(dt.date(), source))
        except KeyboardInterrupt:
            logger.info("Summarisation cancelled by user")
    if publish:
        publish_summary(summary, dt, source)
    else:
        logger.info(f"Summary:\n{summary.to_markdown()}")
