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
    return parser.parse_args()


STRINGS_PATH = "homeassistant/components/{}/strings.json"
ENTITY_COMPONENT_PREFIX = tuple(f"component::{domain}::" for domain in Platform)


def run():
    """Clean translations."""
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

    update_keys = {
        key: f"[%key:{merged[value]}%]"
        for key, value in flattened_translations.items()
        if merged[value] != key
    }

    components = sorted({key.split("::")[1] for key in update_keys})

    strings = {}

    for component in components:
        comp_strings_path = Path(STRINGS_PATH.format(component))
        strings[component] = json.loads(comp_strings_path.read_text())

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
        comp_strings_path.write_text(json.dumps(strings[component], indent=2))

    return 0
