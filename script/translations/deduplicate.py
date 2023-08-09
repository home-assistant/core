"""Deduplicate translations in strings.json."""


import argparse
import json
from pathlib import Path

from homeassistant.const import Platform

from . import upload
from .develop import flatten_translations
from .util import get_base_arg_parser


def get_arguments() -> argparse.Namespace:
    """Get parsed passed in arguments."""
    parser = get_base_arg_parser()
    parser.add_argument(
        "--limit-reference",
        "--lr",
        action="store_true",
        help="Only allow references to same strings.json or common.",
    )
    return parser.parse_args()


STRINGS_PATH = "homeassistant/components/{}/strings.json"
ENTITY_COMPONENT_PREFIX = tuple(f"component::{domain}::" for domain in Platform)


def run():
    """Clean translations."""
    args = get_arguments()
    translations = upload.generate_upload_data()
    flattened_translations = flatten_translations(translations)
    flattened_translations = {
        key: value
        for key, value in flattened_translations.items()
        # Skip existing references
        if not value.startswith("[%key:")
    }

    primary = {}
    secondary = {}

    for key, value in flattened_translations.items():
        if key.startswith("common::"):
            primary[value] = key
        elif key.startswith(ENTITY_COMPONENT_PREFIX):
            primary.setdefault(value, key)
        else:
            secondary.setdefault(value, key)

    merged = {**secondary, **primary}

    # Questionable translations are ones that are duplicate but are not referenced
    # by the common strings.json or strings.json from an entity component.
    questionable = set(secondary.values())
    suggest_new_common = set()
    update_keys = {}

    for key, value in flattened_translations.items():
        if merged[value] == key or key.startswith("common::"):
            continue

        key_integration = key.split("::")[1]

        key_to_reference = merged[value]
        key_to_reference_integration = key_to_reference.split("::")[1]
        is_common = key_to_reference.startswith("common::")

        # If we want to only add references to own integrations
        # but not include entity integrations
        if (
            args.limit_reference
            and (key_integration != key_to_reference_integration and not is_common)
            # Do not create self-references in entity integrations
            or key_integration in Platform.__members__.values()
        ):
            continue

        if (
            # We don't want integrations to reference arbitrary other integrations
            key_to_reference in questionable
            # Allow reference own integration
            and key_to_reference_integration != key_integration
        ):
            suggest_new_common.add(value)
            continue

        update_keys[key] = f"[%key:{key_to_reference}%]"

    if suggest_new_common:
        print("Suggested new common words:")
        for key in sorted(suggest_new_common):
            print(key)

    components = sorted({key.split("::")[1] for key in update_keys})

    strings = {}

    for component in components:
        comp_strings_path = Path(STRINGS_PATH.format(component))
        strings[component] = json.loads(comp_strings_path.read_text(encoding="utf-8"))

    for path, value in update_keys.items():
        parts = path.split("::")
        parts.pop(0)
        component = parts.pop(0)
        to_write = strings[component]
        while len(parts) > 1:
            try:
                to_write = to_write[parts.pop(0)]
            except KeyError:
                print(to_write)
                raise

        to_write[parts.pop(0)] = value

    for component in components:
        comp_strings_path = Path(STRINGS_PATH.format(component))
        comp_strings_path.write_text(
            json.dumps(
                strings[component],
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    return 0
