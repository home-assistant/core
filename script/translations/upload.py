#!/usr/bin/env python3
"""Merge all translation sources into a single JSON file."""
import json
import os
import pathlib
import re
import subprocess

from .const import CLI_2_DOCKER_IMAGE, CORE_PROJECT_ID, INTEGRATIONS_DIR
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
            f"lokalise/lokalise-cli-2:{CLI_2_DOCKER_IMAGE}",
            # Lokalise command
            "lokalise2",
            "--token",
            get_lokalise_token(),
            "--project-id",
            CORE_PROJECT_ID,
            "file",
            "upload",
            "--file",
            CONTAINER_FILE,
            "--lang-iso",
            LANG_ISO,
            "--convert-placeholders=false",
            "--replace-modified",
        ],
    )
    print()

    if run.returncode != 0:
        raise ExitApp("Failed to download translations")


def generate_upload_data():
    """Generate the data for uploading."""
    translations = json.loads((INTEGRATIONS_DIR.parent / "strings.json").read_text())
    translations["component"] = {}

    for path in INTEGRATIONS_DIR.glob(f"*{os.sep}strings*.json"):
        component = path.parent.name
        match = FILENAME_FORMAT.search(path.name)
        platform = match.group("suffix") if match else None

        parent = translations["component"].setdefault(component, {})

        if platform:
            platforms = parent.setdefault("platform", {})
            parent = platforms.setdefault(platform, {})

        parent.update(json.loads(path.read_text()))

    return translations


def run():
    """Run the script."""
    if get_current_branch() != "dev" and os.environ.get("AZURE_BRANCH") != "dev":
        raise ExitApp(
            "Please only run the translations upload script from a clean checkout of dev."
        )

    translations = generate_upload_data()

    LOCAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_FILE.write_text(json.dumps(translations, indent=4, sort_keys=True))

    run_upload_docker()

    return 0
