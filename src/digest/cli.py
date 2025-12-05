from typer import Typer

from digest.agents.hansard_summariser.cli import cli as hansard_cli

cli = Typer()
cli.add_typer(hansard_cli, name="hansard")


if __name__ == "__main__":
    cli()
