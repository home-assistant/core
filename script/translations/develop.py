"""Compile the current translation strings files for testing."""
import argparse
import json
from pathlib import Path
import re
from shutil import rmtree
import sys

from . import download, upload
from .const import INTEGRATIONS_DIR
from .util import get_base_arg_parser


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
            elif isinstance(v, str):
                common_key = "::".join(key_stack)
                flattened_translations[common_key] = v
                key_stack.pop()
        else:
            stack.pop()
            if key_stack:
                key_stack.pop()

    return flattened_translations


def substitute_translation_references(integration_strings, flattened_translations):
    """Recursively processes all translation strings for the integration."""
    result = {}
    for key, value in integration_strings.items():
        if isinstance(value, dict):
            sub_dict = substitute_translation_references(value, flattened_translations)
            result[key] = sub_dict
        elif isinstance(value, str):
            result[key] = substitute_reference(value, flattened_translations)

    return result


def substitute_reference(value, flattened_translations):
    """Substitute localization key references in a translation string."""
    matches = re.findall(r"\[\%key:([a-z0-9_]+(?:::(?:[a-z0-9-_])+)+)\%\]", value)
    if not matches:
        return value

    new = value
    for key in matches:
        if key in flattened_translations:
            new = new.replace(
                f"[%key:{key}%]",
                # New value can also be a substitution reference
                substitute_reference(
                    flattened_translations[key], flattened_translations
                ),
            )
        else:
            print(f"Invalid substitution key '{key}' found in string '{value}'")
            sys.exit(1)

    return new


def run_single(translations, flattened_translations, integration):
    """Run the script for a single integration."""
    print(f"Generating translations for {integration}")

    if integration not in translations["component"]:
        print("Integration has no strings.json")
        sys.exit(1)

    integration_strings = translations["component"][integration]

    translations["component"][integration] = substitute_translation_references(
        integration_strings, flattened_translations
    )

    if download.DOWNLOAD_DIR.is_dir():
        rmtree(str(download.DOWNLOAD_DIR))

    download.DOWNLOAD_DIR.mkdir(parents=True)

    (download.DOWNLOAD_DIR / "en.json").write_text(
        json.dumps({"component": {integration: translations["component"][integration]}})
    )

    download.write_integration_translations()


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
