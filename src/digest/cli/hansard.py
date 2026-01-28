from asyncio import Runner
from datetime import datetime
from typing import Annotated

from loguru import logger
from typer import Argument, Option, Typer

from digest.services.hansard import create_hansard_summary, publish_hansard_summary
from digest.sources.hansard.constants import HansardSourceName
from digest.sources.hansard.main import get_hansard_data_source

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
    data_source = get_hansard_data_source()
    with Runner() as runner:
        try:
            summary = runner.run(create_hansard_summary(dt.date(), source, data_source))
            if summary is None:
                return

            if publish:
                runner.run(publish_hansard_summary(summary, dt.date(), source))
            else:
                logger.info(f"Summary:\n{summary.to_markdown()}")
        except KeyboardInterrupt:
            logger.info("Summarisation cancelled by user")
