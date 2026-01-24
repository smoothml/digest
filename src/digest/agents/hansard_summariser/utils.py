"""Utility functions for the Hansard summariser agent."""

import re


def strip_quote_references(text: str) -> str:
    """Strip quote references from text.

    Removes patterns like [ref: a333.1/5] that are used internally for
    grounding summaries but should not appear in the final output.

    Args:
        text: Text containing quote references.

    Returns:
        Text with quote references removed.
    """
    return re.sub(r"\s*\[ref:\s*[^\]]+\]", "", text)
