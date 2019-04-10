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


COMPONENTS_PATH = pathlib.Path('homeassistant/components')


def validate_dependency(path, dependency, loaded, loading):
    """Validate dependency is exist and no circular dependency."""
    dep_path = path.parent / dependency
    return validate_integration(dep_path, loaded, loading)


def validate_integration(path, loaded, loading):
    """Validate that an integrations has a valid manifest."""
    errors = []
    path = pathlib.Path(path)

    manifest_path = path / 'manifest.json'

    if not manifest_path.is_file():
        errors.append('Manifest file {} not found'.format(manifest_path))
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
        if dep in loaded:
            continue
        if dep in loading:
            errors.append("Found circular dependency {} in {}".format(
                dep, path
            ))
            continue
        loading.add(dep)

        errors.extend(validate_dependency(path, dep, loaded, loading))

    loaded.add(path.name)
    return errors


def validate_all():
    """Validate all integrations."""
    invalid = []

    for fil in COMPONENTS_PATH.iterdir():
        if fil.is_file() or fil.name == '__pycache__':
            continue

        errors = validate_integration(fil, set(), set())

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
