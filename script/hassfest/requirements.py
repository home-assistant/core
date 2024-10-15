"""Validate requirements."""

from __future__ import annotations

from collections import deque
from functools import cache
import json
import os
import re
import subprocess
import sys
from typing import Any

from awesomeversion import AwesomeVersion, AwesomeVersionStrategy
from tqdm import tqdm

import homeassistant.util.package as pkg_util
from script.gen_requirements_all import (
    EXCLUDED_REQUIREMENTS_ALL,
    normalize_package_name,
)

from .model import Config, Integration

PACKAGE_REGEX = re.compile(
    r"^(?:--.+\s)?([-_,\.\w\d\[\]]+)(==|>=|<=|~=|!=|<|>|===)*(.*)$"
)
PIP_REGEX = re.compile(r"^(--.+\s)?([-_\.\w\d]+.*(?:==|>=|<=|~=|!=|<|>|===)?.*$)")
PIP_VERSION_RANGE_SEPARATOR = re.compile(r"^(==|>=|<=|~=|!=|<|>|===)?(.*)$")

IGNORE_STANDARD_LIBRARY_VIOLATIONS = {
    # Integrations which have standard library requirements.
    "slide",
    "suez_water",
}


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Handle requirements for integrations."""
    # Check if we are doing format-only validation.
    if not config.requirements:
        for integration in integrations.values():
            validate_requirements_format(integration)
        return

    # check for incompatible requirements

    disable_tqdm = bool(config.specific_integrations or os.environ.get("CI"))

    for integration in tqdm(integrations.values(), disable=disable_tqdm):
        validate_requirements(integration)


def validate_requirements_format(integration: Integration) -> bool:
    """Validate requirements format.

    Returns if valid.
    """
    start_errors = len(integration.errors)

    for req in integration.requirements:
        if " " in req:
            integration.add_error(
                "requirements",
                f'Requirement "{req}" contains a space',
            )
            continue

        if not (match := PACKAGE_REGEX.match(req)):
            integration.add_error(
                "requirements",
                f'Requirement "{req}" does not match package regex pattern',
            )
            continue
        pkg, sep, version = match.groups()

        if integration.core and sep != "==":
            integration.add_error(
                "requirements",
                f'Requirement {req} need to be pinned "<pkg name>==<version>".',
            )
            continue

        if not version:
            continue

        if integration.core:
            for part in version.split(";", 1)[0].split(","):
                version_part = PIP_VERSION_RANGE_SEPARATOR.match(part)
                if (
                    version_part
                    and AwesomeVersion(version_part.group(2)).strategy
                    == AwesomeVersionStrategy.UNKNOWN
                ):
                    integration.add_error(
                        "requirements",
                        f"Unable to parse package version ({version}) for {pkg}.",
                    )
                    continue

    return len(integration.errors) == start_errors


def validate_requirements(integration: Integration) -> None:
    """Validate requirements."""
    if not validate_requirements_format(integration):
        return

    integration_requirements = set()
    integration_packages = set()
    for req in integration.requirements:
        package = normalize_package_name(req)
        if not package:
            integration.add_error(
                "requirements",
                f"Failed to normalize package name from requirement {req}",
            )
            return
        if package in EXCLUDED_REQUIREMENTS_ALL:
            continue
        integration_requirements.add(req)
        integration_packages.add(package)

    if integration.disabled:
        return

    install_ok = install_requirements(integration, integration_requirements)

    if not install_ok:
        return

    all_integration_requirements = get_requirements(integration, integration_packages)

    if integration_requirements and not all_integration_requirements:
        integration.add_error(
            "requirements",
            f"Failed to resolve requirements {integration_requirements}",
        )
        return

    # Check for requirements incompatible with standard library.
    standard_library_violations = set()
    for req in all_integration_requirements:
        if req in sys.stdlib_module_names:
            standard_library_violations.add(req)

    if (
        standard_library_violations
        and integration.domain not in IGNORE_STANDARD_LIBRARY_VIOLATIONS
    ):
        integration.add_error(
            "requirements",
            (
                f"Package {req} has dependencies {standard_library_violations} which "
                "are not compatible with the Python standard library"
            ),
        )
    elif (
        not standard_library_violations
        and integration.domain in IGNORE_STANDARD_LIBRARY_VIOLATIONS
    ):
        integration.add_error(
            "requirements",
            (
                f"Integration {integration.domain} no longer has requirements which are"
                " incompatible with the Python standard library, remove it from "
                "IGNORE_STANDARD_LIBRARY_VIOLATIONS"
            ),
        )


@cache
def get_pipdeptree() -> dict[str, dict[str, Any]]:
    """Get pipdeptree output. Cached on first invocation.

    {
        "flake8-docstring": {
            "key": "flake8-docstrings",
            "package_name": "flake8-docstrings",
            "installed_version": "1.5.0"
            "dependencies": {"flake8"}
        }
    }
    """
    deptree = {}

    for item in json.loads(
        subprocess.run(
            ["pipdeptree", "-w", "silence", "--json"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    ):
        deptree[item["package"]["key"]] = {
            **item["package"],
            "dependencies": {dep["key"] for dep in item["dependencies"]},
        }
    return deptree


def get_requirements(integration: Integration, packages: set[str]) -> set[str]:
    """Return all (recursively) requirements for an integration."""
    deptree = get_pipdeptree()

    all_requirements = set()

    to_check = deque(packages)

    while to_check:
        package = to_check.popleft()

        if package in all_requirements:
            continue

        all_requirements.add(package)

        item = deptree.get(package)

        if item is None:
            # Only warn if direct dependencies could not be resolved
            if package in packages:
                integration.add_error(
                    "requirements", f"Failed to resolve requirements for {package}"
                )
            continue

        to_check.extend(item["dependencies"])

    return all_requirements


def install_requirements(integration: Integration, requirements: set[str]) -> bool:
    """Install integration requirements.

    Return True if successful.
    """
    deptree = get_pipdeptree()

    for req in requirements:
        match = PIP_REGEX.search(req)

        if not match:
            integration.add_error(
                "requirements",
                f"Failed to parse requirement {req} before installation",
            )
            continue

        install_args = match.group(1)
        requirement_arg = match.group(2)

        is_installed = False

        normalized = normalize_package_name(requirement_arg)

        if normalized and "==" in requirement_arg:
            ver = requirement_arg.split("==")[-1]
            item = deptree.get(normalized)
            is_installed = bool(item and item["installed_version"] == ver)

        if not is_installed:
            try:
                is_installed = pkg_util.is_installed(req)
            except ValueError:
                is_installed = False

        if is_installed:
            continue

        args = ["uv", "pip", "install", "--quiet"]
        if install_args:
            args.append(install_args)
        args.append(requirement_arg)
        try:
            result = subprocess.run(args, check=True, capture_output=True, text=True)
        except subprocess.SubprocessError:
            integration.add_error(
                "requirements",
                f"Requirement {req} failed to install",
            )
        else:
            # Clear the pipdeptree cache if something got installed
            if "Successfully installed" in result.stdout:
                get_pipdeptree.cache_clear()

    if integration.errors:
        return False

    return True
