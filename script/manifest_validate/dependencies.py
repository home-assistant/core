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


# Allowed components to be referend without being a dependency
ALLOWED_USED_COMPONENTS = {
    'persistent_notification',
}


def validate_dependencies(integration: Integration):
    """Validate all dependencies."""
    # Find usage of hass.components
    referenced = grep_dir(integration.path, "**/*.py",
                          r"hass\.components\.(\w+)")
    referenced -= ALLOWED_USED_COMPONENTS
    referenced -= set(integration.dependencies)

    if referenced:
        for domain in sorted(referenced):
            integration.errors.append(
                "Using component {} but it's not a dependency".format(domain))


def validate_all(integrations: Dict[str, Integration]):
    """Validate all dependencies."""
    # check for non-existing dependencies
    for integration in integrations.values():
        if not integration.manifest:
            continue

        validate_dependencies(integration)

        # check that all referenced dependencies exist
        for dep in integration.dependencies:
            if dep not in integrations:
                integration.errors.append(
                    "Dependency {} does not exist"
                )
