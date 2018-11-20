#!/usr/bin/env python3
"""Merge all translation sources into a single JSON file."""
import glob
import itertools
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


def find_strings_files():
    """Return the paths of the strings source files."""
    return itertools.chain(
        glob.iglob("strings*.json"),
        glob.iglob("*{}strings*.json".format(os.sep)),
    )


def get_component_platform(path):
    """Get the component and platform name from the path."""
    directory, filename = os.path.split(path)
    match = FILENAME_FORMAT.search(filename)
    suffix = match.group('suffix') if match else None
    if directory:
        return directory, suffix
    else:
        return suffix, None


def get_translation_dict(translations, component, platform):
    """Return the dict to hold component translations."""
    if not component:
        return translations['component']

    if component not in translations['component']:
        translations['component'][component] = {}

    if not platform:
        return translations['component'][component]

    if 'platform' not in translations['component'][component]:
        translations['component'][component]['platform'] = {}

    if platform not in translations['component'][component]['platform']:
        translations['component'][component]['platform'][platform] = {}

    return translations['component'][component]['platform'][platform]


def main():
    """Run the script."""
    if not os.path.isfile("requirements_all.txt"):
        print("Run this from HA root dir")
        return

    root = os.getcwd()
    os.chdir(os.path.join("homeassistant", "components"))

    translations = {
        'component': {}
    }

    paths = find_strings_files()
    for path in paths:
        component, platform = get_component_platform(path)
        parent = get_translation_dict(translations, component, platform)
        strings = load_json(path)
        parent.update(strings)

    os.chdir(root)

    os.makedirs("build", exist_ok=True)

    save_json(
        os.path.join("build", "translations-upload.json"), translations)


if __name__ == '__main__':
    main()
