from string import Template
from textwrap import dedent

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
