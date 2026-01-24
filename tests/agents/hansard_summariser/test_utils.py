"""Tests for digest.agents.hansard_summariser.utils module."""

import pytest

from digest.agents.hansard_summariser.utils import strip_quote_references


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param(
            'He said "hello" [ref: a333.1/5].',
            'He said "hello".',
            id="simple",
        ),
        pytest.param(
            "First quote [ref: a333.1/5] and second quote [ref: a269.2/1].",
            "First quote and second quote.",
            id="multiple",
        ),
        pytest.param(
            "Combined quote [ref: a333.1/1; a333.1/2].",
            "Combined quote.",
            id="semicolon_separator",
        ),
        pytest.param(
            "Range quote [ref: a333.1/6‑7].",
            "Range quote.",
            id="range_with_en_dash",
        ),
        pytest.param(
            "Range quote [ref: a333.1/6-7].",
            "Range quote.",
            id="range_with_hyphen",
        ),
        pytest.param(
            "Quote [ref:  a333.1/5].",
            "Quote.",
            id="extra_whitespace",
        ),
        pytest.param(
            "Quote [ref: a333.1/5].",
            "Quote.",
            id="removes_preceding_space",
        ),
        pytest.param(
            "This text has no references at all.",
            "This text has no references at all.",
            id="no_references",
        ),
        pytest.param(
            "",
            "",
            id="empty_string",
        ),
        pytest.param(
            "The outcome was positive [ref: a380.2/5]",
            "The outcome was positive",
            id="at_end_without_period",
        ),
        pytest.param(
            (
                'The Secretary of State said "It is the most successful auction '
                'round in European history" [ref: a289.7/1], and announced a '
                '"landmark £1 billion clean energy supply chain fund" [ref: a289.9/1].'
            ),
            (
                'The Secretary of State said "It is the most successful auction '
                'round in European history", and announced a '
                '"landmark £1 billion clean energy supply chain fund".'
            ),
            id="real_world",
        ),
        pytest.param(
            (
                "First line with quote [ref: a100.0/1].\n"
                "Second line with quote [ref: a200.0/1].\n"
                "Third line without reference."
            ),
            (
                "First line with quote.\n"
                "Second line with quote.\n"
                "Third line without reference."
            ),
            id="multiline",
        ),
    ],
)
def test_strip_quote_references(text: str, expected: str) -> None:
    """Strip quote references from text."""
    assert strip_quote_references(text) == expected
