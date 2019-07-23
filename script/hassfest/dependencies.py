"""Validate dependencies."""
import pathlib
import re
from typing import Set, Dict

from .model import Integration


def grep_dir(path: pathlib.Path, glob_pattern: str, search_pattern: str) \
        -> Set[str]:
    """Recursively go through a dir and it's children and find the regex."""
    pattern = re.compile(search_pattern)
    found = set()

    for fil in path.glob(glob_pattern):
        if not fil.is_file():
            continue

        for match in pattern.finditer(fil.read_text()):
            found.add(match.groups()[0])

    return found


ALLOWED_USED_COMPONENTS = {
    # This component will always be set up
    'persistent_notification',
    # These allow to register things without being set up
    'conversation',
    'frontend',
    'hassio',
    'system_health',
    'websocket_api',
}


def validate_dependencies(integration: Integration):
    """Validate all dependencies."""
    # Find usage of hass.components
    referenced = grep_dir(integration.path, "**/*.py",
                          r"hass\.components\.(\w+)")
    referenced -= ALLOWED_USED_COMPONENTS
    referenced -= set(integration.manifest['dependencies'])
    referenced -= set(integration.manifest.get('after_dependencies', []))

    if referenced:
        for domain in sorted(referenced):
            print("Warning: {} references integration {} but it's not a "
                  "dependency".format(integration.domain, domain))
            # Not enforced yet.
            # integration.add_error(
            #     'dependencies',
            #     "Using component {} but it's not a dependency".format(domain)
            # )


def validate(integrations: Dict[str, Integration], config):
    """Handle dependencies for integrations."""
    # check for non-existing dependencies
    for integration in integrations.values():
        if not integration.manifest:
            continue

        validate_dependencies(integration)

        # check that all referenced dependencies exist
        for dep in integration.manifest['dependencies']:
            if dep not in integrations:
                integration.add_error(
                    'dependencies',
                    "Dependency {} does not exist".format(dep)
                )
