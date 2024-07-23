"""Find translation keys that are in Lokalise but no longer defined in source."""

import argparse

from .const import CORE_PROJECT_ID, FRONTEND_DIR, FRONTEND_PROJECT_ID, INTEGRATIONS_DIR
from .error import ExitApp
from .lokalise import get_api
from .util import get_base_arg_parser, load_json_from_path


def get_arguments() -> argparse.Namespace:
    """Get parsed passed in arguments."""
    parser = get_base_arg_parser()
    parser.add_argument(
        "--target",
        type=str,
        default="core",
        choices=["core", "frontend"],
    )
    return parser.parse_args()


def find_extra(base, translations, path_prefix, missing_keys):
    """Find all keys that are in translations but not in base."""
    for key, value in translations.items():
        cur_path = f"{path_prefix}::{key}" if path_prefix else key

        # Value is either a dict or a string
        if isinstance(value, dict):
            base_search = None if base is None else base.get(key)
            find_extra(base_search, value, cur_path, missing_keys)

        elif base is None or key not in base:
            missing_keys.append(cur_path)


def find_core():
    """Find all missing keys in core."""
    missing_keys = []

    for int_dir in INTEGRATIONS_DIR.iterdir():
        strings = int_dir / "strings.json"

        if not strings.is_file():
            continue

        translations = int_dir / "translations" / "en.json"

        strings_json = load_json_from_path(strings)
        if translations.is_file():
            translations_json = load_json_from_path(translations)
        else:
            translations_json = {}

        find_extra(
            strings_json, translations_json, f"component::{int_dir.name}", missing_keys
        )

    return missing_keys


def find_frontend():
    """Find all missing keys in frontend."""
    if not FRONTEND_DIR.is_dir():
        raise ExitApp(f"Unable to find frontend at {FRONTEND_DIR}")

    source = FRONTEND_DIR / "src/translations/en.json"
    translated = FRONTEND_DIR / "translations/frontend/en.json"

    missing_keys = []
    find_extra(
        load_json_from_path(source),
        load_json_from_path(translated),
        "",
        missing_keys,
    )
    return missing_keys


def run():
    """Clean translations."""
    args = get_arguments()
    if args.target == "frontend":
        missing_keys = find_frontend()
        lokalise = get_api(FRONTEND_PROJECT_ID)
    else:
        missing_keys = find_core()
        lokalise = get_api(CORE_PROJECT_ID)

    if not missing_keys:
        print("No missing translations!")
        return 0

    print(f"Found {len(missing_keys)} extra keys")

    # We can't query too many keys at once, so limit the number to 50.
    for i in range(0, len(missing_keys), 50):
        chunk = missing_keys[i : i + 50]

        key_data = lokalise.keys_list({"filter_keys": ",".join(chunk), "limit": 1000})
        if len(key_data) != len(chunk):
            print(
                f"Lookin up key in Lokalise returns {len(key_data)} results, expected {len(chunk)}"
            )

        if not key_data:
            continue

        print(f"Deleting {len(key_data)} keys:")
        for key in key_data:
            print(" -", key["key_name"]["web"])
        print()
        while input("Type YES to delete these keys: ") != "YES":
            pass

        print(lokalise.keys_delete_multiple([key["key_id"] for key in key_data]))
        print()

    return 0
