# Digest

Condensing complex things into a simple digest.

Install dependencies:

```bash
uv sync --all-groups --all-extras
```

Lint and format:

```bash
uv run ruff check --fix
uv run ruff format
uv run mypy .
```

Summarise and publish Hansard debates:

```bash
uv run digest hansard summarise YYYY-MM-DD --publish
```

Run site:

```bash
hugo serve -s sites/<site-name> --gc
```

Deploy a site — publishes [standard.site](https://standard.site) records to the AT Protocol with [Sequoia](https://sequoia.pub), builds with Hugo, then rsyncs:

```bash
task deploy
```

This requires the `sequoia` CLI: `npm i -g sequoia-cli`, then `sequoia login`.
