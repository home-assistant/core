"""Shared requirement policies and package-name normalization."""

import re

# Requirements which can't be installed on all systems because they
# rely on additional system packages. Requirements listed in
# EXCLUDED_REQUIREMENTS_ALL will be commented-out in
# requirements_all.txt.
EXCLUDED_REQUIREMENTS_ALL = {
    "atenpdu",  # depends on pysnmp which is not maintained at this time
    "beewi-smartclim",  # depends on bluepy
    "bluepy",
    "evdev",
}

PACKAGE_REGEX = re.compile(r"^(?:--.+\s)?([-_\.\w\d]+).*==.+$")


def _normalize_package_name(package_name: str) -> str:
    """Normalize a package name."""
    # pipdeptree needs lowercase and dash instead of underscore or period as separator
    return package_name.lower().replace("_", "-").replace(".", "-")


def normalize_package_name(requirement: str) -> str:
    """Return a normalized package name from a requirement string."""
    match = PACKAGE_REGEX.search(requirement)
    if not match:
        return ""

    # pipdeptree needs lowercase and dash instead of underscore or period as separator
    return _normalize_package_name(match.group(1))
