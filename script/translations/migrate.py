"""Migrate things."""
import json
from pprint import pprint

from .const import INTEGRATIONS_DIR
from .lokalise import get_api

MIGRATED = {}


def run():
    """Migrate translations."""
    to_migrate = {}

    for integration in INTEGRATIONS_DIR.iterdir():
        strings_file = integration / "strings.json"
        if not strings_file.is_file():
            continue

        if integration.name in MIGRATED:
            continue

        strings = json.loads(strings_file.read_text())

        if "title" in strings:
            from_key = f"component::{integration.name}::config::title"
            to_key = f"component::{integration.name}::title"
            to_migrate[from_key] = to_key

    updates = []

    lokalise = get_api()

    print("Gathering IDs")

    for from_key, to_key in to_migrate.items():
        key_data = lokalise.keys_list({"filter_keys": from_key})
        if len(key_data) != 1:
            print(
                f"Lookin up {from_key} key in Lokalise returns {len(key_data)} results, expected 1"
            )
            continue

        updates.append({"key_id": key_data[0]["key_id"], "key_name": to_key})

    pprint(updates)

    print()
    print("Updating keys")
    pprint(lokalise.keys_bulk_update(updates).json())
