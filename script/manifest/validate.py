#!/usr/bin/env python3
"""Validate all integrations have manifests and that they are valid."""
import json
import pathlib
import sys

import voluptuous as vol
from voluptuous.humanize import humanize_error


MANIFEST_SCHEMA = vol.Schema({
    vol.Required('domain'): str,
    vol.Required('name'): str,
    vol.Required('documentation'): str,
    vol.Required('requirements'): [str],
    vol.Required('dependencies'): [str],
    vol.Required('codeowners'): [str],
})


components_path = pathlib.Path('homeassistant/components')


def validate_integration(path):
    """Validate that an integrations has a valid manifest."""
    errors = []
    path = pathlib.Path(path)

    manifest_path = path / 'manifest.json'

    if not manifest_path.is_file():
        errors.append('File manifest.json not found')
        return errors  # Fatal error

    try:
        manifest = json.loads(manifest_path.read_text())
    except ValueError as err:
        errors.append("Manifest contains invalid JSON: {}".format(err))
        return errors  # Fatal error

    try:
        MANIFEST_SCHEMA(manifest)
    except vol.Invalid as err:
        errors.append(humanize_error(manifest, err))

    if manifest['domain'] != path.name:
        errors.append('Domain does not match dir name')

    for dep in manifest['dependencies']:
        dep_manifest = path.parent / dep / 'manifest.json'
        if not dep_manifest.is_file():
            errors.append("Unable to find dependency {}".format(dep))

    return errors


def validate_all():
    """Validate all integrations."""
    invalid = []

    for fil in components_path.iterdir():
        if fil.is_file() or fil.name == '__pycache__':
            continue

        errors = validate_integration(fil)

        if errors:
            invalid.append((fil, errors))

    if not invalid:
        return 0

    print("Found invalid manifests")
    print()

    for integration, errors in invalid:
        print(integration)
        for error in errors:
            print("*", error)
        print()

    return 1


if __name__ == '__main__':
    sys.exit(validate_all())
