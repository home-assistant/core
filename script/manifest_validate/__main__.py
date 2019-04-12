"""Validate manifests."""
import pathlib
import sys

from .model import Integration
from . import dependencies, manifest


COMPONENTS_PATH = pathlib.Path('homeassistant/components')


def main():
    """Validate manifests."""
    integrations = {}
    invalid = []

    for fil in COMPONENTS_PATH.iterdir():
        if fil.is_file() or fil.name == '__pycache__':
            continue

        integration = Integration(fil)
        integration.load_manifest()
        integrations[integration.domain] = integration

    manifest.validate_all(integrations)
    dependencies.validate_all(integrations)

    invalid = [itg for itg in integrations.values() if itg.errors]

    if not invalid:
        return 0

    print("Found invalid integrations")
    print()

    for integration in sorted(invalid, key=lambda itg: itg.domain):
        print(integration.domain)
        for error in integration.errors:
            print("*", error)
        print()

    return 1


if __name__ == "__main__":
    sys.exit(main())
