"""Find translation keys that are in Lokalise but no longer defined in source."""
import json

from .const import INTEGRATIONS_DIR
from .lokalise import get_api


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


def find():
    """Find all missing keys."""
    missing_keys = []

    for int_dir in INTEGRATIONS_DIR.iterdir():
        strings = int_dir / "strings.json"

        if not strings.is_file():
            continue

        translations = int_dir / ".translations" / "en.json"

        strings_json = json.loads(strings.read_text())
        translations_json = json.loads(translations.read_text())

        find_extra(
            strings_json, translations_json, f"component::{int_dir.name}", missing_keys
        )

    return missing_keys


def run():
    """Clean translations."""
    missing_keys = find()

    if not missing_keys:
        print("No missing translations!")
        return 0

    lokalise = get_api()

    key_data = lokalise.keys_list(
        {"filter_keys": ",".join(missing_keys), "limit": 1000}
    )
    if len(key_data) != len(missing_keys):
        print(
            f"Lookin up key in Lokalise returns {len(key_data)} results, expected {len(missing_keys)}"
        )
        return 1

    print(f"Deleting {len(missing_keys)} keys:")
    for key in missing_keys:
        print(" -", key)
    print()
    while input("Type YES to delete these keys: ") != "YES":
        pass

    print(lokalise.keys_delete_multiple([key["key_id"] for key in key_data]))

    return 0
