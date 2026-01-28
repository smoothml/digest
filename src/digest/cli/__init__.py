from typer import Typer

from digest.cli.hansard import cli as hansard_cli

cli = Typer()
cli.add_typer(hansard_cli, name="hansard")
