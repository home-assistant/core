"""Translation utils."""

import argparse
import json
import os
import pathlib
import subprocess
from typing import Any

from .error import ExitApp, JSONDecodeErrorWithPath


def get_base_arg_parser() -> argparse.ArgumentParser:
    """Get a base argument parser."""
    parser = argparse.ArgumentParser(description="Home Assistant Translations")
    parser.add_argument(
        "action",
        type=str,
        choices=[
            "clean",
            "deduplicate",
            "develop",
            "download",
            "frontend",
            "migrate",
            "upload",
        ],
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
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stdout=subprocess.PIPE,
            check=True,
        )
        .stdout.decode()
        .strip()
    )


def load_json_from_path(path: pathlib.Path) -> Any:
    """Load JSON from path."""
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as err:
        raise JSONDecodeErrorWithPath(err.msg, err.doc, err.pos, path) from err


def flatten_translations(translations):
    """Flatten all translations."""
    stack = [iter(translations.items())]
    key_stack = []
    flattened_translations = {}
    while stack:
        for k, v in stack[-1]:
            key_stack.append(k)
            if isinstance(v, dict):
                stack.append(iter(v.items()))
                break
            if isinstance(v, str):
                common_key = "::".join(key_stack)
                flattened_translations[common_key] = v
                key_stack.pop()
        else:
            stack.pop()
            if key_stack:
                key_stack.pop()

    return flattened_translations
