"""Validate requirements."""
import operator
import subprocess
from typing import Dict, Set

from stdlib_list import stdlib_list

from homeassistant.const import REQUIRED_PYTHON_VER
import homeassistant.util.package as pkg_util

from .model import Integration

SUPPORTED_PYTHON_TUPLES = [
    REQUIRED_PYTHON_VER[:2],
    tuple(map(operator.add, REQUIRED_PYTHON_VER, (0, 1, 0)))[:2],
]
SUPPORTED_PYTHON_VERSIONS = [
    ".".join(map(str, version_tuple)) for version_tuple in SUPPORTED_PYTHON_TUPLES
]


def validate(integrations: Dict[str, Integration], config):
    """Handle requirements for integrations."""
    # check for incompatible requirements
    for integration in integrations.values():
        if not integration.manifest:
            continue

        validate_requirements(integration)


def validate_requirements(integration: Integration):
    """Validate requirements."""
    install_ok = install_requirements(integration)

    if not install_ok:
        return

    integration_requirements = get_requirements(integration)

    if integration.requirements and not integration_requirements:
        integration.add_error(
            "requirements",
            f"Failed to resolve requirements {integration.requirements}, check PyPI name",
        )
        return

    for version in SUPPORTED_PYTHON_VERSIONS:
        std_libs = set(stdlib_list(version))

        for req in integration_requirements:
            if req in std_libs:
                integration.add_error(
                    "requirements",
                    f"Package {req} is not compatible with Python {version} standard library",
                )


def get_requirements(integration: Integration) -> Set[str]:
    """Return all (recursively) requirements for an integration."""
    requirements = integration.requirements

    all_requirements = set()

    for req in requirements:
        package = req.split("==")[0]
        result = subprocess.run(
            ["pipdeptree", "-w", "silence", "--packages", package],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            integration.add_error(
                "requirements", f"Failed to resolve requirements for {req}"
            )
            continue

        # parse output to get a set of package names
        output = result.stdout
        lines = output.split("\n")
        parent = lines[0].split("==")[0]  # the first line is the parent package
        if parent:
            all_requirements.add(parent)

        for line in lines[1:]:  # skip the first line which we already processed
            line = line.strip()
            line = line.lstrip("- ")
            package = line.split("[")[0]
            package = package.strip()
            if not package:
                continue
            all_requirements.add(package)

    return all_requirements


def install_requirements(integration: Integration) -> bool:
    """Install integration requirements.

    Return True if successful.
    """
    requirements = integration.requirements

    for req in requirements:
        if pkg_util.is_installed(req):
            continue

        ret = pkg_util.install_package(req)

        if not ret:
            integration.add_error(
                "requirements", f"Requirement {req} failed to install",
            )

    if integration.errors:
        return False

    return True
