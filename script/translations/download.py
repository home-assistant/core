#!/usr/bin/env python3
"""Merge all translation sources into a single JSON file."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from typing import Any

from .const import CLI_2_DOCKER_IMAGE, CORE_PROJECT_ID, INTEGRATIONS_DIR
from .error import ExitApp
from .util import flatten_translations, get_lokalise_token, load_json_from_path

FILENAME_FORMAT = re.compile(r"strings\.(?P<suffix>\w+)\.json")
DOWNLOAD_DIR = Path("build/translations-download").absolute()


def run_download_docker():
    """Run the Docker image to download the translations."""
    print("Running Docker to download latest translations.")
    run = subprocess.run(
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

    if run.returncode != 0:
        raise ExitApp("Failed to download translations")


def save_json(filename: Path, data: list | dict) -> None:
    """Save JSON data to a file."""
    filename.write_text(json.dumps(data, sort_keys=True, indent=4), encoding="utf-8")


def get_component_path(lang, component) -> Path | None:
    """Get the component translation path."""
    if (Path("homeassistant") / "components" / component).is_dir():
        return (
            Path("homeassistant")
            / "components"
            / component
            / "translations"
            / f"{lang}.json"
        )
    return None


def get_platform_path(lang, component, platform) -> Path:
    """Get the platform translation path."""
    return (
        Path("homeassistant")
        / "components"
        / component
        / "translations"
        / f"{platform}.{lang}.json"
    )


def get_component_translations(translations):
    """Get the component level translations."""
    translations = translations.copy()
    translations.pop("platform", None)

    return translations


def save_language_translations(lang, translations):
    """Distribute the translations for this language."""
    components = translations.get("component", {})
    for component, component_translations in components.items():
        base_translations = get_component_translations(component_translations)
        if base_translations:
            if (path := get_component_path(lang, component)) is None:
                print(
                    f"Skipping {lang} for {component}, as the integration doesn't seem to exist."
                )
                continue
            if not (
                Path("homeassistant") / "components" / component / "strings.json"
            ).exists():
                print(
                    f"Skipping {lang} for {component}, as the integration doesn't have a strings.json file."
                )
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            base_translations = pick_keys(component, base_translations)
            save_json(path, base_translations)

        if "platform" not in component_translations:
            continue

        for platform, platform_translations in component_translations[
            "platform"
        ].items():
            path = get_platform_path(lang, component, platform)
            path.parent.mkdir(parents=True, exist_ok=True)
            save_json(path, platform_translations)


def write_integration_translations():
    """Write integration translations."""
    for lang_file in DOWNLOAD_DIR.glob("*.json"):
        lang = lang_file.stem
        translations = load_json_from_path(lang_file)
        save_language_translations(lang, translations)


def delete_old_translations():
    """Delete old translations."""
    for fil in INTEGRATIONS_DIR.glob("*/translations/*"):
        fil.unlink()


def get_current_keys(component: str) -> dict[str, Any]:
    """Get the current keys for a component."""
    strings_path = Path("homeassistant") / "components" / component / "strings.json"
    return load_json_from_path(strings_path)


def pick_keys(component: str, translations: dict[str, Any]) -> dict[str, Any]:
    """Pick the keys that are in the current strings."""
    flat_translations = flatten_translations(translations)
    flat_current_keys = flatten_translations(get_current_keys(component))
    flatten_result = {}
    for key in flat_current_keys:
        if key in flat_translations:
            flatten_result[key] = flat_translations[key]
    result = {}
    for key, value in flatten_result.items():
        parts = key.split("::")
        d = result
        for part in parts[:-1]:
            if part not in d:
                d[part] = {}
            d = d[part]
        d[parts[-1]] = value
    return result


def run():
    """Run the script."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    run_download_docker()

    delete_old_translations()

    write_integration_translations()

    return 0
