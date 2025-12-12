# api2gn/cli.py
import click

from api2gn.commands import cmd_list_parsers, run


@click.group(name="parser")
def parser_cli():
    """Commandes de gestion des parsers API2GN"""
    pass


parser_cli.add_command(cmd_list_parsers)
parser_cli.add_command(run)
