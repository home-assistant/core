"""Find translation keys that are in Lokalise but no longer defined in source."""
import json
import pathlib
import sys

import requests

INTEGRATION_DIR = pathlib.Path("homeassistant/components")
PROJECT_ID = "130246255a974bd3b5e8a1.51616605"


class Lokalise:
    """Lokalise API."""

    def __init__(self, project_id, token):
        """Initialize Lokalise API."""
        self.project_id = project_id
        self.token = token

    def request(self, method, path, data):
        """Make a request to the Lokalise API."""
        method = method.upper()
        kwargs = {"headers": {"x-api-token": self.token}}
        if method == "GET":
            kwargs["params"] = data
        else:
            kwargs["json"] = data

        req = requests.request(
            method,
            f"https://api.lokalise.com/api2/projects/{self.project_id}/{path}",
            **kwargs,
        )
        req.raise_for_status()
        return req.json()

    def keys_list(self, params={}):
        """Fetch key ID from a name.

        https://app.lokalise.com/api2docs/curl/#transition-list-all-keys-get
        """
        return self.request("GET", "keys", params)["keys"]

    def keys_delete_multiple(self, key_ids):
        """Delete multiple keys.

        https://app.lokalise.com/api2docs/curl/#transition-delete-multiple-keys-delete
        """
        return self.request("DELETE", "keys", {"keys": key_ids})


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

    for int_dir in INTEGRATION_DIR.iterdir():
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

    lokalise = Lokalise(PROJECT_ID, pathlib.Path(".lokalise_token").read_text().strip())

    to_delete = []

    for key in missing_keys:
        print("Processing", key)
        key_data = lokalise.keys_list({"filter_keys": key})
        if len(key_data) != 1:
            print(
                f"Lookin up key in Lokalise returns {len(key_data)} results, expected 1"
            )
            continue
        to_delete.append(key_data[0]["key_id"])

    print("Deleting keys:", ", ".join(map(str, to_delete)))
    print(lokalise.keys_delete_multiple(to_delete))
    return 0


if __name__ == "__main__":
    sys.exit(run())
