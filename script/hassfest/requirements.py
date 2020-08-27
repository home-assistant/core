"""Validate requirements."""
import operator
import subprocess
import sys
from typing import Dict, Set

from script.gen_requirements_all import COMMENT_REQUIREMENTS
from stdlib_list import stdlib_list
from tqdm import tqdm

from homeassistant.const import REQUIRED_PYTHON_VER
import homeassistant.util.package as pkg_util

from .model import Config, Integration

SUPPORTED_PYTHON_TUPLES = [
    REQUIRED_PYTHON_VER[:2],
    tuple(map(operator.add, REQUIRED_PYTHON_VER, (0, 1, 0)))[:2],
]
SUPPORTED_PYTHON_VERSIONS = [
    ".".join(map(str, version_tuple)) for version_tuple in SUPPORTED_PYTHON_TUPLES
]
IGNORE_PACKAGES = {commented.lower() for commented in COMMENT_REQUIREMENTS}

STD_LIBS = {version: set(stdlib_list(version)) for version in SUPPORTED_PYTHON_VERSIONS}


def validate(integrations: Dict[str, Integration], config: Config):
    """Handle requirements for integrations."""
    # check for incompatible requirements
    for integration in tqdm(integrations.values()):
        if not integration.manifest:
            continue

        validate_requirements(integration)


def validate_requirements(integration: Integration):
    """Validate requirements."""
    integration_requirements = set()
    for req in integration.requirements:
        package = normalize_package_name(req)
        if package in IGNORE_PACKAGES:
            continue
        integration_requirements.add(req)

    install_ok = install_requirements(integration, integration_requirements)

    if not install_ok:
        return

    all_integration_requirements = get_requirements(
        integration, integration_requirements
    )

    if integration_requirements and not all_integration_requirements:
        integration.add_error(
            "requirements",
            f"Failed to resolve requirements {integration_requirements}, check PyPI name",
        )
        return

    # Check for requirements incompatible with standard library.
    for version, std_libs in STD_LIBS.items():
        for req in all_integration_requirements:
            if req in std_libs:
                integration.add_error(
                    "requirements",
                    f"Package {req} is not compatible with Python {version} standard library",
                )


def get_requirements(integration: Integration, requirements: Set[str]) -> Set[str]:
    """Return all (recursively) requirements for an integration."""
    all_requirements = set()

    for req in requirements:
        package = normalize_package_name(req)
        try:
            result = subprocess.run(
                ["pipdeptree", "-w", "silence", "--packages", package],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.SubprocessError:
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


def install_requirements(integration: Integration, requirements: Set[str]) -> bool:
    """Install integration requirements.

    Return True if successful.
    """
    for req in requirements:
        try:
            is_installed = pkg_util.is_installed(req)
        except ValueError:
            integration.add_error(
                "requirements",
                f"Invalid requirement {req}",
            )
            continue

        if is_installed:
            continue

        args = [sys.executable, "-m", "pip", "install", "--quiet", req]
        try:
            subprocess.run(args, check=True)
        except subprocess.SubprocessError:
            integration.add_error(
                "requirements",
                f"Requirement {req} failed to install",
            )

    if integration.errors:
        return False

    return True


def normalize_package_name(requirement: str) -> str:
    """Return a normalized package name from a requirement string."""
    package = requirement.split("==")[0]  # remove version pinning
    package = package.split("[")[0]  # remove potential require extras
    # replace undescore with dash to work with pipdeptree
    package = package.replace("_", "-")
    package = package.lower()  # normalize casing

    return package
