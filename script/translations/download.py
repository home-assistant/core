#!/usr/bin/env python3
"""Merge all translation sources into a single JSON file."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any

from .const import CLI_2_DOCKER_IMAGE, CORE_PROJECT_ID, INTEGRATIONS_DIR
from .error import ExitApp
from .util import (
    flatten_translations,
    get_lokalise_token,
    load_json_from_path,
    substitute_references,
)

DOWNLOAD_DIR = Path("build/translations-download").absolute()


def run_download_docker() -> None:
    """Run the Docker image to download the translations."""
    print("Running Docker to download latest translations.")
    result = subprocess.run(
        [
            "docker",
            "run",
            "-v",
            f"{DOWNLOAD_DIR}:/opt/dest/locale",
            "--rm",
            f"lokalise/lokalise-cli-2:{CLI_2_DOCKER_IMAGE}",
            # Lokalise command
            "lokalise2",
            "--token",
            get_lokalise_token(),
            "--project-id",
            CORE_PROJECT_ID,
            "file",
            "download",
            CORE_PROJECT_ID,
            "--original-filenames=false",
            "--replace-breaks=false",
            "--filter-data",
            "nonfuzzy",
            "--disable-references",
            "--export-empty-as",
            "skip",
            "--format",
            "json",
            "--unzip-to",
            "/opt/dest",
        ],
        check=False,
    )
    print()

    if result.returncode != 0:
        raise ExitApp("Failed to download translations")


def save_json(filename: Path, data: list | dict) -> None:
    """Save JSON data to a file."""
    filename.write_text(json.dumps(data, sort_keys=True, indent=4), encoding="utf-8")


def filter_translations(translations: dict[str, Any], strings: dict[str, Any]) -> None:
    """Remove translations that are not in the original strings."""
    for key in list(translations.keys()):
        if key not in strings:
            translations.pop(key)
            continue

        if isinstance(translations[key], dict):
            if not isinstance(strings[key], dict):
                translations.pop(key)
                continue
            filter_translations(translations[key], strings[key])
            if not translations[key]:
                translations.pop(key)
                continue


def save_language_translations(lang: str, translations: dict[str, Any]) -> None:
    """Save translations for a single language."""
    components = translations.get("component", {})

    flattened_translations = flatten_translations(translations)

    for component, component_translations in components.items():
        # Remove legacy platform translations
        component_translations.pop("platform", None)

        if not component_translations:
            continue

        component_path = Path("homeassistant") / "components" / component
        if not component_path.is_dir():
            print(
                f"Skipping {lang} for {component}, as the integration doesn't seem to exist."
            )
            continue

        strings_path = component_path / "strings.json"
        if not strings_path.exists():
            print(
                f"Skipping {lang} for {component}, as the integration doesn't have a strings.json file."
            )
            continue
        strings = load_json_from_path(strings_path)

        path = component_path / "translations" / f"{lang}.json"
        path.parent.mkdir(parents=True, exist_ok=True)

        component_translations = substitute_references(
            component_translations, flattened_translations, fail_on_missing=False
        )

        filter_translations(component_translations, strings)

        save_json(path, component_translations)


def save_integrations_translations() -> None:
    """Save integrations translations."""
    for lang_file in DOWNLOAD_DIR.glob("*.json"):
        lang = lang_file.stem
        translations = load_json_from_path(lang_file)
        save_language_translations(lang, translations)


def delete_old_translations() -> None:
    """Delete old translations."""
    for fil in INTEGRATIONS_DIR.glob("*/translations/*"):
        fil.unlink()


def run() -> None:
    """Run the script."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    run_download_docker()

    delete_old_translations()

    save_integrations_translations()

    return 0
