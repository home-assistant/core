"""Translation utils."""

import argparse
import json
import os
import pathlib
import re
import subprocess
from typing import Any

from .error import ExitApp, JSONDecodeErrorWithPath, MissingReference


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


def substitute_reference(value: str, flattened_translations: dict[str, str]) -> str:
    """Substitute localization key references in a translation string."""
    matches = re.findall(r"\[\%key:([a-z0-9_]+(?:::(?:[a-z0-9-_])+)+)\%\]", value)
    if not matches:
        return value

    new = value
    for key in matches:
        if key in flattened_translations:
            # New value can also be a substitution reference
            substituted = substitute_reference(
                flattened_translations[key], flattened_translations
            )
            new = new.replace(f"[%key:{key}%]", substituted)
        else:
            raise MissingReference(key)

    return new


def substitute_references(
    translations: dict[str, Any],
    substitutions: dict[str, str],
    *,
    fail_on_missing: bool,
) -> dict[str, Any]:
    """Recursively substitute references for all translation strings."""
    result = {}
    for key, value in translations.items():
        if isinstance(value, dict):
            sub_dict = substitute_references(
                value, substitutions, fail_on_missing=fail_on_missing
            )
            if sub_dict:
                result[key] = sub_dict
        elif isinstance(value, str):
            try:
                substituted = substitute_reference(value, substitutions)
            except MissingReference as err:
                if fail_on_missing:
                    raise ExitApp(
                        f"Missing reference '{err.reference_key}' in translation for key '{key}'"
                    ) from err
                continue
            result[key] = substituted

    return result
