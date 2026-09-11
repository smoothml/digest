from string import Template
from textwrap import dedent
from typing import Literal

ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh"]
"""Reasoning effort levels accepted by the `gpt-5.6-luna` OpenAI model.

A different `model` value may accept a different set of effort levels. For
example, the rollback model `gpt-5-2025-08-07` accepts `minimal`, which is
not part of this literal, and rejects `none` and `xhigh`, which are.
"""

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
