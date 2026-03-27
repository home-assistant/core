#!/usr/bin/env python3
"""Merge all translation sources into a single JSON file."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import time
from typing import Any
from zipfile import ZipFile

import lokalise
import requests

from .const import CORE_PROJECT_ID, INTEGRATIONS_DIR
from .error import ExitApp
from .util import (
    flatten_translations,
    get_base_arg_parser,
    get_lokalise_token,
    load_json_from_path,
    substitute_references,
)

DOWNLOAD_DIR = Path("build/translations-download").absolute()


POLL_INTERVAL = 5


def get_arguments() -> argparse.Namespace:
    """Get parsed passed in arguments."""
    parser = get_base_arg_parser()
    parser.add_argument(
        "--async-start",
        action="store_true",
        help="Start an async download and return the process ID.",
    )
    parser.add_argument(
        "--process-id",
        type=str,
        help="Process ID to wait for, then download and unzip the result.",
    )
    return parser.parse_args()


def get_client() -> lokalise.Client:
    """Get an authenticated Lokalise client."""
    return lokalise.Client(get_lokalise_token())


def start_async_download(client: lokalise.Client) -> str:
    """Start an async download and return the process ID."""
    process = client.download_files_async(
        CORE_PROJECT_ID,
        {
            "format": "json",
            "original_filenames": False,
            "replace_breaks": False,
            "filter_data": "nonfuzzy",
            "disable_references": True,
            "export_empty_as": "skip",
        },
    )
    return process.process_id


def wait_for_process(client: lokalise.Client, process_id: str) -> str:
    """Wait for a queued process to complete and return the process download URL."""
    while True:
        process_info = client.queued_process(CORE_PROJECT_ID, process_id)
        # Current status of the process. Can be queued, pre_processing, running,
        # post_processing, cancelled, finished or failed.
        status = process_info.status
        additional_info = ""
        if process_info.details is not None and (details := dict(process_info.details)):
            if (
                status == "running"
                and (done := details.get("items_processed")) is not None
                and (total := details.get("items_to_process")) is not None
            ):
                additional_info = f" ({done}/{total})"
            elif status == "finished":
                additional_info = f" total_keys={details.get('total_number_of_keys')}"
            else:
                additional_info = f" details={details}"
        print(f"Process {process_id}: status={status}{additional_info}")

        if status == "finished":
            return process_info.details["download_url"]
        if status in ("cancelled", "failed"):
            raise ExitApp(
                f"Process {process_id} ended with status: {status}{additional_info}"
            )

        time.sleep(POLL_INTERVAL)


def download_and_unzip(bundle_url: str) -> None:
    """Download a zip bundle and extract it to the download directory."""
    print("Downloading translations from lokalise...")
    response = requests.get(bundle_url, timeout=120)
    response.raise_for_status()

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with ZipFile(io.BytesIO(response.content)) as zf:
        zf.extractall(DOWNLOAD_DIR)

    print(f"Extracted translations to {DOWNLOAD_DIR}")


def fetch_translations(client: lokalise.Client, process_id: str) -> None:
    """Wait for a process to finish, then download and unzip the bundle."""
    download_url = wait_for_process(client, process_id)
    download_and_unzip(download_url)


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


def run() -> int:
    """Run the script."""
    args = get_arguments()
    client = get_client()

    process_id = args.process_id

    if not process_id:
        # if no process ID provided, start a new async download and print the process ID
        process_id = start_async_download(client)
        print(f"Async download started. Process ID: {process_id}")

        if args.async_start:
            # If --async-start is provided, exit after starting the download
            return 0

    fetch_translations(client, process_id)
    delete_old_translations()
    save_integrations_translations()
    return 0
