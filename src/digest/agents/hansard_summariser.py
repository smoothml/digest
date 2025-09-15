from asyncio import Runner
from datetime import date, datetime
from string import Template
from textwrap import dedent
from typing import Annotated

from loguru import logger
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from typer import Argument, Option, Typer

from digest.settings import openai_provider
from digest.site import create_post, format_post, get_all_tags
from digest.sources.hansard.constants import HansardSourceType
from digest.sources.hansard.main import get_hansard_data_source

cli = Typer(name="hansard")

SUMMARY_SYSTEM_PROMPT = dedent(
    """
    <persona>
    You are a precise, impartial, and methodical communicator.
    You value factual accuracy over flourish, are transparent about uncertainty, and avoid conjecture.
    Your writing is clear, succinct, and accessible to a general audience without oversimplifying.
    You consistently use British English and maintain a calm, even tone.
    You disclose limitations when information is missing and never ascribe motives.
    You clearly attribute statements to named speakers and distinguish quotes from summaries.
    </persona>
    <task>
    Summarise one day's debates from a single UK parliamentary chamber given in XML format.
    Produce a politically neutral, fact-focused briefing that helps a reader quickly understand what was discussed, who argued what, and what outcomes (if any) occurred.
    Support key statements with short, verbatim quotes that include the source sentence reference ID from the input.

    **Input assumptions & parsing**
    Input: An XML string covering a single chamber (e.g. the House of Commons) on a single day.
    Treat the transcript order as chronological. Extract metadata when present (date, chamber, sitting type, debate headings/titles, speaker names/roles/parties, timestamps, divisions).
    Identify and group content into topics/debates (e.g., statements, questions, bill stages, UQs, SO statements, motions, Westminster Hall/Lords Grand Committee where applicable).
    Preserve exact speaker names and roles as given. If a role/party is not provided, omit rather than guess.
    Sentence reference IDs: when quoting, include the exact sentence reference ID(s) from the input. DO NOT fabricate IDs.

    **Summary requirements**
    High-level section: 3-5 concise bullets capturing the main themes/events of the day.
    Detailed section: organised by debate/topic in transcript order. For each topic:
    - Brief context (what the debate was about).
    - Who participated and, where available, their roles (e.g., Secretary of State, Shadow Minister) without inferring party lines if not stated.
    - Key arguments and points from different sides, neutrally described.
    - Outcomes: decisions taken, withdrawals, ministerial commitments, division results (Ayes/Noes and numbers), or “no decision recorded”.
    - Next steps if stated (e.g., “to be laid,” “report back,” “scheduled for further consideration”).
    Evidence: Back up significant claims about positions, arguments, or outcomes with **short direct quotes** (≤25 words each) followed by the sentence reference ID, formatted as `[ref: <ID>]`. Use quotes sparingly but sufficiently - aim for at least one supporting quote per major claim or subsection.
    Give no opinion or judgement. Avoid evaluative adjectives/adverbs (e.g., “strong,” “weak,” “controversial”) unless they appear in a quoted phrase.
    Do not speculate. If information is not present, write “not stated in the transcript.”
    Use British English spelling and parliamentary terminology accurately. Expand acronyms on first use if not obvious from context.

    **Citation & quotation rules**
    Quotations must be verbatim from the transcript and enclosed in straight double quotes.
    Immediately include the originating sentence reference ID in the form `[ref: <ID>]` adjacent to the quote.
    If multiple sentences are quoted, include each ID (e.g., `[ref: <ID1>, <ID2>]`).
    Do not cite paraphrases as quotes.
    Where a single claim is supported by more than one quote, prefer the most representative one.

    **Style constraints**
    Keep the high-level summary crisp (ideally ≤120 words total).
    In the detailed section, prefer short paragraphs and bullet points to improve scanability.
    Attribute positions to speakers by name and role (if available) without asserting party unless explicitly provided.
    Do not include links unless the input provides them.
    </task>
    <output_format>
    Your output should comprise a 3-5 sentence high-level summary of the day's proceedings focussing on the key discussions and decisions, followed by a 1-2 paragraph detailed summary of each debate or topic.
    Each detailed summary should be given a title and the detail should be a 1-2 paragraph summary of the key arguments made for and against, the outcome, and next steps where applicable.
    Always include direct quotes (including paragraph ID) to back up claims.
    DO NOT start detailed paragraphs with "<word>: <detailed_summary>". For example, DO NOT start with "Context: <context>". Instead start with "<context>".
    </output_format>
    """
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
DETAILED_SUMMARY_POST_TEMPLATE = Template(
    dedent(
        """
        ### ${title}
        ${summary}
        """
    )
)
SUMMARY_POST_TEMPLATE = Template(
    dedent(
        """
        ## High-Level Summary
        ${high_level}

        ## Detailed Summary
        ${detailed}
        """
    )
)


class DetailedSummary(BaseModel):
    """Detailed summary of a debate or topic."""

    title: str = Field(..., description="A short title for the debate or topic.")
    summary: str = Field(
        ...,
        description="A 1-2 paragraph summary of the key arguments made for and against, the outcome, and next steps where applicable. Always include direct quotes (including paragraph ID) to back up claims.",
    )


class Summary(BaseModel):
    """Summary output model."""

    high_level: str = Field(
        ...,
        description="3-5 sentences giving a high-level summary of the day's proceedings. Focus on the key discussions and decisions.",
    )
    detail: list[DetailedSummary] = Field(
        ...,
        description="A list of debates and topics discussed in the day's proceedings, each with a 1-2 paragraph summary of the key arguments made for and against, the outcome, and next steps where applicable. Always include direct quotes (including paragraph ID) to back up claims.",
    )

    @staticmethod
    def _format_detailed_summary(ds: DetailedSummary) -> str:
        return DETAILED_SUMMARY_POST_TEMPLATE.safe_substitute(
            title=ds.title,
            summary=ds.summary,
        ).strip()

    def to_markdown(self) -> str:
        return SUMMARY_POST_TEMPLATE.safe_substitute(
            high_level=self.high_level,
            detailed="\n\n".join(
                [self._format_detailed_summary(ds) for ds in self.detail]
            ),
        ).strip()


hansard_data_source = get_hansard_data_source()

model = OpenAIModel(
    "gpt-5-mini-2025-08-07",
    provider=openai_provider,
)
summary_agent = Agent(model, system_prompt=SUMMARY_SYSTEM_PROMPT, output_type=Summary)
tag_agent = Agent(model, deps_type=set[str], output_type=list[str])


@tag_agent.system_prompt
def create_tag_system_prompt(ctx: RunContext[set[str]]) -> str:
    existing_tags = "\n".join([f"- {tag}" for tag in ctx.deps])
    return TAG_SYSTEM_PROMPT_TEMPLATE.safe_substitute(existing_tags=existing_tags)


async def get_hansard_summary(
    dt: date, source: HansardSourceType = HansardSourceType.DEBATES
) -> Summary:
    debate = hansard_data_source.get(dt, source)
    logger.info(f"Generating summary for {source} on {dt}.")
    result = await summary_agent.run(debate.xml_string)
    return result.output


async def get_tags(summary: str, existing_tags: set[str]) -> list[str]:
    result = await tag_agent.run(summary, deps=existing_tags)
    tags = [tag.lower() for tag in result.output]
    logger.info(f"Tags: {', '.join(tags)}")
    return tags


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
    summary_str = summary.to_markdown()
    if publish:
        existing_tags = get_all_tags("hansard")
        with Runner() as runner:
            try:
                tags = runner.run(get_tags(summary_str, existing_tags))
            except KeyboardInterrupt:
                logger.info("Tag generation cancelled by user")
        post_content = format_post(
            summary_str,
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
    else:
        logger.info(f"Summary:\n{summary}")
