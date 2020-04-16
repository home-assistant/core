"""Migrate things."""
import json
from pprint import pprint

from .const import CORE_PROJECT_ID, FRONTEND_PROJECT_ID, INTEGRATIONS_DIR
from .lokalise import get_api


def create_lookup(results):
    """Create a lookup table by key name."""
    return {key["key_name"]["web"]: key for key in results}


def rename_keys(to_migrate):
    """Rename keys.

    to_migrate is Dict[from_key] = to_key.
    """
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


def migrate_project_keys_translations(from_project_id, to_project_id, to_migrate):
    """Migrate keys and translations from one project to another.

    to_migrate is Dict[from_key] = to_key.
    """
    from_lokalise = get_api(from_project_id)
    to_lokalise = get_api(to_project_id, True)

    from_key_data = from_lokalise.keys_list(
        {"filter_keys": ",".join(to_migrate), "include_translations": 1}
    )
    if len(from_key_data) != len(to_migrate):
        print(
            f"Lookin up keys in Lokalise returns {len(from_key_data)} results, expected {len(to_migrate)}"
        )
        return

    from_key_lookup = create_lookup(from_key_data)

    # Fetch keys in target
    # We are going to skip migrating existing keys
    to_key_data = to_lokalise.keys_list(
        {"filter_keys": ",".join(to_migrate.values()), "include_translations": 1}
    )
    existing = set(create_lookup(to_key_data))

    missing = [key for key in to_migrate.values() if key not in existing]

    if not missing:
        print("All keys to migrate exist already, nothing to do")
        return

    print("Creating", ", ".join(missing))
    to_key_lookup = create_lookup(
        to_lokalise.keys_create(
            [{"key_name": key, "platforms": ["web"]} for key in missing]
        )
    )

    updates = []

    for from_key, to_key in to_migrate.items():
        # If it is not in lookup, it already existed, skipping it.
        if to_key not in to_key_lookup:
            continue

        updates.append(
            {
                "key_id": to_key_lookup[to_key]["key_id"],
                "translations": [
                    {
                        "language_iso": from_translation["language_iso"],
                        "translation": from_translation["translation"],
                        "is_reviewed": from_translation["is_reviewed"],
                        "is_fuzzy": from_translation["is_fuzzy"],
                    }
                    for from_translation in from_key_lookup[from_key]["translations"]
                ],
            }
        )

    print("Updating")
    pprint(updates)
    print()
    print()
    pprint(to_lokalise.keys_bulk_update(updates))


def find_and_rename_keys():
    """Find and rename keys in core."""
    to_migrate = {}

    for integration in INTEGRATIONS_DIR.iterdir():
        strings_file = integration / "strings.json"
        if not strings_file.is_file():
            continue

        strings = json.loads(strings_file.read_text())

        if "title" in strings.get("config", {}):
            from_key = f"component::{integration.name}::config::title"
            to_key = f"component::{integration.name}::title"
            to_migrate[from_key] = to_key

    rename_keys(to_migrate)


def find_different_languages():
    """Find different supported languages."""
    core_api = get_api(CORE_PROJECT_ID)
    frontend_api = get_api(FRONTEND_PROJECT_ID)

    core_languages = {lang["lang_iso"] for lang in core_api.languages_list()}
    frontend_languages = {lang["lang_iso"] for lang in frontend_api.languages_list()}

    print("Core minus frontend", core_languages - frontend_languages)
    print("Frontend minus core", frontend_languages - core_languages)


def run():
    """Migrate translations."""
    # find_different_languages()
    migrate_project_keys_translations(
        FRONTEND_PROJECT_ID,
        CORE_PROJECT_ID,
        {
            "domain::binary_sensor": "component::binary_sensor::title",
            "domain::sensor": "component::sensor::title",
        },
    )

    return 0
