"""Translation utils."""
import argparse
import os
import pathlib
import subprocess

from .error import ExitApp


def get_base_arg_parser():
    """Get a base argument parser."""
    parser = argparse.ArgumentParser(description="Home Assistant Translations")
    parser.add_argument(
        "action", type=str, choices=["download", "clean", "upload", "develop"]
    )
    parser.add_argument("--debug", action="store_true", help="Enable log output")
    return parser


def get_lokalise_token():
    """Get lokalise token."""
    token = os.environ.get("LOKALISE_TOKEN")

    if token is not None:
        return token

    token_file = pathlib.Path(".lokalise_token")

    if not token_file.is_file():
        raise ExitApp(
            "Lokalise token not found in env LOKALISE_TOKEN or file .lokalise_token"
        )

    return token_file.read_text().strip()


def get_current_branch():
    """Get current branch."""
    return (
        subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], stdout=subprocess.PIPE
        )
        .stdout.decode()
        .strip()
    )
