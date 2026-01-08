# Project Overview
The purpose of Digest is to generate AI summaries of large complex data sources.
The currently supported source is Hansard, the full written record of UK parlimentary debates.

The project uses the following tech stack:
* Python 3.13
* [`uv`](https://docs.astral.sh/uv/) for Python environment management.
* [Pydantic AI](https://ai.pydantic.dev/) for agent implementation.
* [Hugo](https://gohugo.io/documentation/) static site generator for publishing summaries.
* [Task](https://taskfile.dev/docs/guide) for running pipelines

Key components:
* `scripts`: Shell scripts called by Task pipeline steps.
* `sites`: Static sites for serving generated summaries.
* `sites/themes`: Git submodules containing themes used for sites.
* `sites/<site-name>`: Hugo site for `<site-name>` following the standard Hugo layout.
* `src/digest`: Main application.
* `src/digest/agents`: Summariser agents.
* `src/digest/sources`: Data source abstractions.
* `tests`: Unit and integration tests for the `digest` application.
* `data`: Raw data examples.