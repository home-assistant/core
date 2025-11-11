"""Compile the current translation strings files for testing."""

import argparse
import json
from pathlib import Path
import sys

from . import download, upload
from .const import INTEGRATIONS_DIR
from .util import flatten_translations, get_base_arg_parser, substitute_references


def valid_integration(integration):
    """Test if it's a valid integration."""
    if not (INTEGRATIONS_DIR / integration).is_dir():
        raise argparse.ArgumentTypeError(
            f"The integration {integration} does not exist."
        )

    return integration


def get_arguments() -> argparse.Namespace:
    """Get parsed passed in arguments."""
    parser = get_base_arg_parser()
    parser.add_argument(
        "--integration", type=valid_integration, help="Integration to process."
    )
    parser.add_argument("--all", action="store_true", help="Process all integrations.")
    return parser.parse_args()


def run_single(translations, flattened_translations, integration):
    """Run the script for a single integration."""
    print(f"Generating translations for {integration}")

    if integration not in translations["component"]:
        print("Integration has no strings.json")
        sys.exit(1)

    integration_strings = translations["component"][integration]

    translations["component"][integration] = substitute_references(
        integration_strings, flattened_translations, fail_on_missing=True
    )

    if download.DOWNLOAD_DIR.is_dir():
        for lang_file in download.DOWNLOAD_DIR.glob("*.json"):
            lang_file.unlink()
    else:
        download.DOWNLOAD_DIR.mkdir(parents=True)

    (download.DOWNLOAD_DIR / "en.json").write_text(
        json.dumps({"component": {integration: translations["component"][integration]}})
    )

    download.save_integrations_translations()


def run():
    """Run the script."""
    args = get_arguments()
    translations = upload.generate_upload_data()
    flattened_translations = flatten_translations(translations)

    if args.all:
        for integration in translations["component"]:
            run_single(translations, flattened_translations, integration)
        print("🌎 Generated translation files for all integrations")
        return 0

    if args.integration:
        integration = args.integration
    else:
        integration = None
        while (
            integration is None
            or not Path(f"homeassistant/components/{integration}").exists()
        ):
            if integration is not None:
                print(f"Integration {integration} doesn't exist!")
                print()
            integration = input("Integration to process: ")

    run_single(translations, flattened_translations, integration)
    return 0
