#!/usr/bin/env python3
"""Merge all translation sources into a single JSON file."""
import glob
import json
import os
import re
from typing import Union, List, Dict

FILENAME_FORMAT = re.compile(r'strings\.(?P<suffix>\w+)\.json')


def load_json(filename: str) \
        -> Union[List, Dict]:
    """Load JSON data from a file and return as dict or list.

    Defaults to returning empty dict if file is not found.
    """
    with open(filename, encoding='utf-8') as fdesc:
        return json.loads(fdesc.read())
    return {}


def save_json(filename: str, data: Union[List, Dict]):
    """Save JSON data to a file.

    Returns True on success.
    """
    data = json.dumps(data, sort_keys=True, indent=4)
    with open(filename, 'w', encoding='utf-8') as fdesc:
        fdesc.write(data)
        return True
    return False


def get_language(path):
    """Get the language code for the given file path."""
    return os.path.splitext(os.path.basename(path))[0]


def get_component_path(lang, component):
    """Get the component translation path."""
    if os.path.isdir(os.path.join("homeassistant", "components", component)):
        return os.path.join(
            "homeassistant", "components", component, ".translations",
            "{}.json".format(lang))
    else:
        return os.path.join(
            "homeassistant", "components", ".translations",
            "{}.{}.json".format(component, lang))


def get_platform_path(lang, component, platform):
    """Get the platform translation path."""
    if os.path.isdir(os.path.join(
            "homeassistant", "components", component, platform)):
        return os.path.join(
            "homeassistant", "components", component, platform,
            ".translations", "{}.json".format(lang))
    else:
        return os.path.join(
            "homeassistant", "components", component, ".translations",
            "{}.{}.json".format(platform, lang))


def get_component_translations(translations):
    """Get the component level translations."""
    translations = translations.copy()
    translations.pop('platform', None)

    return translations


def save_language_translations(lang, translations):
    """Distribute the translations for this language."""
    components = translations.get('component', {})
    for component, component_translations in components.items():
        base_translations = get_component_translations(component_translations)
        if base_translations:
            path = get_component_path(lang, component)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            save_json(path, base_translations)

        for platform, platform_translations in component_translations.get(
                'platform', {}).items():
            path = get_platform_path(lang, component, platform)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            save_json(path, platform_translations)


def main():
    """Run the script."""
    if not os.path.isfile("requirements_all.txt"):
        print("Run this from HA root dir")
        return

    paths = glob.iglob("build/translations-download/*.json")
    for path in paths:
        lang = get_language(path)
        translations = load_json(path)
        save_language_translations(lang, translations)


if __name__ == '__main__':
    main()
