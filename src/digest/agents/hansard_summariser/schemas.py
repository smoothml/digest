from pydantic import BaseModel, Field

from digest.agents.hansard_summariser.constants import (
    DETAILED_SUMMARY_POST_TEMPLATE,
    SUMMARY_POST_TEMPLATE,
)


class DetailedSummary(BaseModel):
    """Detailed summary of a debate or topic."""

    title: str = Field(..., description="A short title for the debate or topic.")
    summary: str = Field(
        ...,
        description="A 1-2 paragraph summary of the key arguments made for and against, the outcome, and next steps where applicable. Always include direct quotes (including paragraph ID) to back up claims.",
    )


class DraftSummary(BaseModel):
    """Draft summary output model."""

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
        """Format the detailed summary.

        Args:
            ds: Detailed summary to format.

        Returns:
            Markdown formatted detailed summary.
        """
        return DETAILED_SUMMARY_POST_TEMPLATE.safe_substitute(
            title=ds.title,
            summary=ds.summary,
        ).strip()

    def to_markdown(self) -> str:
        """Convert the summary to markdown.

        Returns:
            Markdown formatted summary.
        """
        return SUMMARY_POST_TEMPLATE.safe_substitute(
            high_level=self.high_level,
            detailed="\n\n".join(
                [self._format_detailed_summary(ds) for ds in self.detail]
            ),
        ).strip()


class FinalSummary(DraftSummary):
    """Final summary output model."""

    quality_report: str = Field(
        ...,
        description="A quality report detailing the changes made to the draft summary.",
    )
