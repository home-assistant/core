"""Validate requirements."""
import operator
import re
import subprocess
import sys
from typing import Dict, Set

from stdlib_list import stdlib_list
from tqdm import tqdm

from homeassistant.const import REQUIRED_PYTHON_VER
import homeassistant.util.package as pkg_util
from script.gen_requirements_all import COMMENT_REQUIREMENTS

from .model import Config, Integration

IGNORE_PACKAGES = {
    commented.lower().replace("_", "-") for commented in COMMENT_REQUIREMENTS
}
PACKAGE_REGEX = re.compile(r"^(?:--.+\s)?([-_\.\w\d]+).*==.+$")
PIP_REGEX = re.compile(r"^(--.+\s)?([-_\.\w\d]+.*(?:==|>=|<=|~=|!=|<|>|===)?.*$)")
SUPPORTED_PYTHON_TUPLES = [
    REQUIRED_PYTHON_VER[:2],
    tuple(map(operator.add, REQUIRED_PYTHON_VER, (0, 1, 0)))[:2],
]
SUPPORTED_PYTHON_VERSIONS = [
    ".".join(map(str, version_tuple)) for version_tuple in SUPPORTED_PYTHON_TUPLES
]
STD_LIBS = {version: set(stdlib_list(version)) for version in SUPPORTED_PYTHON_VERSIONS}


def normalize_package_name(requirement: str) -> str:
    """Return a normalized package name from a requirement string."""
    match = PACKAGE_REGEX.search(requirement)
    if not match:
        return ""

    # pipdeptree needs lowercase and dash instead of underscore as separator
    package = match.group(1).lower().replace("_", "-")

    return package


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
    integration_packages = set()
    for req in integration.requirements:
        package = normalize_package_name(req)
        if not package:
            integration.add_error(
                "requirements",
                f"Failed to normalize package name from requirement {req}",
            )
            return
        if package in IGNORE_PACKAGES:
            continue
        integration_requirements.add(req)
        integration_packages.add(package)

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
    for version, std_libs in STD_LIBS.items():
        for req in all_integration_requirements:
            if req in std_libs:
                integration.add_error(
                    "requirements",
                    f"Package {req} is not compatible with Python {version} standard library",
                )


def get_requirements(integration: Integration, packages: Set[str]) -> Set[str]:
    """Return all (recursively) requirements for an integration."""
    all_requirements = set()

    for package in packages:
        try:
            result = subprocess.run(
                ["pipdeptree", "-w", "silence", "--packages", package],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.SubprocessError:
            integration.add_error(
                "requirements", f"Failed to resolve requirements for {package}"
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
            is_installed = False

        if is_installed:
            continue

        match = PIP_REGEX.search(req)

        if not match:
            integration.add_error(
                "requirements",
                f"Failed to parse requirement {req} before installation",
            )
            continue

        install_args = match.group(1)
        requirement_arg = match.group(2)

        args = [sys.executable, "-m", "pip", "install", "--quiet"]
        if install_args:
            args.append(install_args)
        args.append(requirement_arg)
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
