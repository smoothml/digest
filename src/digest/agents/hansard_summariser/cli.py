from asyncio import Runner
from datetime import datetime
from typing import Annotated

from loguru import logger
from typer import Argument, Option, Typer

from digest.sources.hansard.constants import SOURCE_NAME_TO_TYPE_MAP, HansardSourceName
from digest.agents.hansard_summariser.agent import get_hansard_summary, publish_summary

cli = Typer(name="hansard")


@cli.command()
def summarise(
    dt: Annotated[
        datetime, Argument(formats=["%Y-%m-%d"], help="Date of debate to summarise.")
    ],
    source: Annotated[
        HansardSourceName, Option(help="Source of debate to summarise.")
    ] = HansardSourceName.COMMONS,
    publish: Annotated[bool, Option(help="Publish summaries as a post.")] = False,
) -> None:
    with Runner() as runner:
        try:
            summary = runner.run(
                get_hansard_summary(dt.date(), SOURCE_NAME_TO_TYPE_MAP[source])
            )
        except KeyboardInterrupt:
            logger.info("Summarisation cancelled by user")
    if publish and summary is not None:
        publish_summary(summary, dt, source)
    elif summary is not None:
        logger.info(f"Summary:\n{summary.to_markdown()}")
    else:
        logger.error(f"No debate found for {dt.date()} {source}")
