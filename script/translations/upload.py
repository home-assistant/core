#!/usr/bin/env python3
"""Merge all translation sources into a single JSON file."""
import json
import os
import pathlib
import re
import subprocess

from .const import DOCKER_IMAGE, INTEGRATIONS_DIR, PROJECT_ID
from .error import ExitApp
from .util import get_current_branch, get_lokalise_token

FILENAME_FORMAT = re.compile(r"strings\.(?P<suffix>\w+)\.json")
LOCAL_FILE = pathlib.Path("build/translations-upload.json").absolute()
CONTAINER_FILE = "/opt/src/build/translations-upload.json"
LANG_ISO = "en"


def run_upload_docker():
    """Run the Docker image to upload the translations."""
    print("Running Docker to upload latest translations.")
    run = subprocess.run(
        [
            "docker",
            "run",
            "-v",
            f"{LOCAL_FILE}:{CONTAINER_FILE}",
            "--rm",
            f"lokalise/lokalise-cli@sha256:{DOCKER_IMAGE}",
            # Lokalise command
            "lokalise",
            "--token",
            get_lokalise_token(),
            "import",
            PROJECT_ID,
            "--file",
            CONTAINER_FILE,
            "--lang_iso",
            LANG_ISO,
            "--convert_placeholders",
            "0",
            "--replace",
            "1",
        ],
    )
    print()

    if run.returncode != 0:
        raise ExitApp("Failed to download translations")


def get_translation_dict(translations, component, platform):
    """Return the dict to hold component translations."""
    translations["component"].setdefault(component, {})

    if not platform:
        return translations["component"][component]

    platforms = translations["component"][component].setdefault("platform", {})

    return platforms.setdefault(platform, {})


def run(args):
    """Run the script."""
    if (
        False
        and get_current_branch() != "dev"
        and os.environ.get("AZURE_BRANCH") != "dev"
    ):
        raise ExitApp(
            "Please only run the translations upload script from a clean checkout of dev."
        )

    translations = {"component": {}}

    for path in INTEGRATIONS_DIR.glob(f"*{os.sep}strings*.json"):
        component = path.parent.name
        match = FILENAME_FORMAT.search(path.name)
        platform = match.group("suffix") if match else None
        parent = get_translation_dict(translations, component, platform)
        parent.update(json.loads(path.read_text()))

    LOCAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_FILE.write_text(json.dumps(translations, indent=4, sort_keys=True))

    run_upload_docker()
