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

PACKAGE_CHECK_VERSION_RANGE = {
    "aiohttp": "SemVer",
    "attrs": "CalVer",
    "grpcio": "SemVer",
    "httpx": "SemVer",
    "mashumaro": "SemVer",
    "pydantic": "SemVer",
    "pyjwt": "SemVer",
    "pytz": "CalVer",
    "typing_extensions": "SemVer",
    "yarl": "SemVer",
}
PACKAGE_CHECK_VERSION_RANGE_EXCEPTIONS: dict[str, dict[str, set[str]]] = {
    # In the form dict("domain": {"package": {"dependency1", "dependency2"}})
    # - domain is the integration domain
    # - package is the package (can be transitive) referencing the dependency
    # - dependencyX should be the name of the referenced dependency
    "ollama": {
        # https://github.com/ollama/ollama-python/pull/445 (not yet released)
        "ollama": {"httpx"}
    },
    "overkiz": {
        # https://github.com/iMicknl/python-overkiz-api/issues/1644 (not yet released)
        "pyoverkiz": {"attrs"},
    },
}

PACKAGE_REGEX = re.compile(
    r"^(?:--.+\s)?([-_,\.\w\d\[\]]+)(==|>=|<=|~=|!=|<|>|===)*(.*)$"
)
PIP_REGEX = re.compile(r"^(--.+\s)?([-_\.\w\d]+.*(?:==|>=|<=|~=|!=|<|>|===)?.*$)")
PIP_VERSION_RANGE_SEPARATOR = re.compile(r"^(==|>=|<=|~=|!=|<|>|===)?(.*)$")

FORBIDDEN_PACKAGES = {
    # Only needed for tests
    "codecov": "not be a runtime dependency",
    # Does blocking I/O and should be replaced by pyserial-asyncio-fast
    # See https://github.com/home-assistant/core/pull/116635
    "pyserial-asyncio": "be replaced by pyserial-asyncio-fast",
    # Only needed for tests
    "pytest": "not be a runtime dependency",
    # Only needed for build
    "setuptools": "not be a runtime dependency",
    # Only needed for build
    "wheel": "not be a runtime dependency",
}
FORBIDDEN_PACKAGE_EXCEPTIONS: dict[str, dict[str, set[str]]] = {
    # In the form dict("domain": {"package": {"reason1", "reason2"}})
    # - domain is the integration domain
    # - package is the package (can be transitive) referencing the dependency
    # - reasonX should be the name of the invalid dependency
    "azure_devops": {
        # https://github.com/timmo001/aioazuredevops/issues/67
        # aioazuredevops > incremental > setuptools
        "incremental": {"setuptools"}
    },
    "blackbird": {
        # https://github.com/koolsb/pyblackbird/issues/12
        # pyblackbird > pyserial-asyncio
        "pyblackbird": {"pyserial-asyncio"}
    },
    "cmus": {
        # https://github.com/mtreinish/pycmus/issues/4
        # pycmus > pbr > setuptools
        "pbr": {"setuptools"}
    },
    "concord232": {
        # https://bugs.launchpad.net/python-stevedore/+bug/2111694
        # concord232 > stevedore > pbr > setuptools
        "pbr": {"setuptools"}
    },
    "edl21": {
        # https://github.com/mtdcr/pysml/issues/21
        # pysml > pyserial-asyncio
        "pysml": {"pyserial-asyncio"}
    },
    "efergy": {
        # https://github.com/tkdrob/pyefergy/issues/46
        # pyefergy > codecov
        # pyefergy > types-pytz
        "pyefergy": {"codecov", "types-pytz"}
    },
    "epson": {
        # https://github.com/pszafer/epson_projector/pull/22
        # epson-projector > pyserial-asyncio
        "epson-projector": {"pyserial-asyncio"}
    },
    "fitbit": {
        # https://github.com/orcasgit/python-fitbit/pull/178
        # but project seems unmaintained
        # fitbit > setuptools
        "fitbit": {"setuptools"}
    },
    "guardian": {
        # https://github.com/jsbronder/asyncio-dgram/issues/20
        # aioguardian > asyncio-dgram > setuptools
        "asyncio-dgram": {"setuptools"}
    },
    "heatmiser": {
        # https://github.com/andylockran/heatmiserV3/issues/96
        # heatmiserV3 > pyserial-asyncio
        "heatmiserv3": {"pyserial-asyncio"}
    },
    "hive": {
        # https://github.com/Pyhass/Pyhiveapi/pull/88
        # pyhive-integration > unasync > setuptools
        "unasync": {"setuptools"}
    },
    "homeassistant_hardware": {
        # https://github.com/zigpy/zigpy/issues/1604
        # universal-silabs-flasher > zigpy > pyserial-asyncio
        "zigpy": {"pyserial-asyncio"},
    },
    "influxdb": {
        # https://github.com/influxdata/influxdb-client-python/issues/695
        # influxdb-client > setuptools
        "influxdb-client": {"setuptools"}
    },
    "insteon": {
        # https://github.com/pyinsteon/pyinsteon/issues/430
        # pyinsteon > pyserial-asyncio
        "pyinsteon": {"pyserial-asyncio"}
    },
    "keba": {
        # https://github.com/jsbronder/asyncio-dgram/issues/20
        # keba-kecontact > asyncio-dgram > setuptools
        "asyncio-dgram": {"setuptools"}
    },
    "lyric": {
        # https://github.com/timmo001/aiolyric/issues/115
        # aiolyric > incremental > setuptools
        "incremental": {"setuptools"}
    },
    "microbees": {
        # https://github.com/microBeesTech/pythonSDK/issues/6
        # microbeespy > setuptools
        "microbeespy": {"setuptools"}
    },
    "minecraft_server": {
        # https://github.com/jsbronder/asyncio-dgram/issues/20
        # mcstatus > asyncio-dgram > setuptools
        "asyncio-dgram": {"setuptools"}
    },
    "mochad": {
        # https://github.com/mtreinish/pymochad/issues/8
        # pymochad > pbr > setuptools
        "pbr": {"setuptools"}
    },
    "monoprice": {
        # https://github.com/etsinko/pymonoprice/issues/9
        # pymonoprice > pyserial-asyncio
        "pymonoprice": {"pyserial-asyncio"}
    },
    "mysensors": {
        # https://github.com/theolind/pymysensors/issues/818
        # pymysensors > pyserial-asyncio
        "pymysensors": {"pyserial-asyncio"}
    },
    "mystrom": {
        # https://github.com/home-assistant-ecosystem/python-mystrom/issues/55
        # python-mystrom > setuptools
        "python-mystrom": {"setuptools"}
    },
    "ness_alarm": {
        # https://github.com/nickw444/nessclient/issues/73
        # nessclient > pyserial-asyncio
        "nessclient": {"pyserial-asyncio"}
    },
    "nx584": {
        # https://bugs.launchpad.net/python-stevedore/+bug/2111694
        # pynx584 > stevedore > pbr > setuptools
        "pbr": {"setuptools"}
    },
    "opnsense": {
        # https://github.com/mtreinish/pyopnsense/issues/27
        # pyopnsense > pbr > setuptools
        "pbr": {"setuptools"}
    },
    "opower": {
        # https://github.com/arrow-py/arrow/issues/1169 (fixed not yet released)
        # opower > arrow > types-python-dateutil
        "arrow": {"types-python-dateutil"}
    },
    "osoenergy": {
        # https://github.com/osohotwateriot/apyosohotwaterapi/pull/4
        # pyosoenergyapi > unasync > setuptools
        "unasync": {"setuptools"}
    },
    "ovo_energy": {
        # https://github.com/timmo001/ovoenergy/issues/132
        # ovoenergy > incremental > setuptools
        "incremental": {"setuptools"}
    },
    "remote_rpi_gpio": {
        # https://github.com/waveform80/colorzero/issues/9
        # gpiozero > colorzero > setuptools
        "colorzero": {"setuptools"}
    },
    "rflink": {
        # https://github.com/aequitas/python-rflink/issues/78
        # rflink > pyserial-asyncio
        "rflink": {"pyserial-asyncio"}
    },
    "system_bridge": {
        # https://github.com/timmo001/system-bridge-connector/pull/78
        # systembridgeconnector > incremental > setuptools
        "incremental": {"setuptools"}
    },
    "travisci": {
        # https://github.com/menegazzo/travispy seems to be unmaintained
        # and unused https://www.home-assistant.io/integrations/travisci
        # travispy > pytest-rerunfailures > pytest
        "pytest-rerunfailures": {"pytest"},
        # travispy > pytest
        "travispy": {"pytest"},
    },
    "zha": {
        # https://github.com/waveform80/colorzero/issues/9
        # zha > zigpy-zigate > gpiozero > colorzero > setuptools
        "colorzero": {"setuptools"},
        # https://github.com/zigpy/zigpy/issues/1604
        # zha > zigpy > pyserial-asyncio
        "zigpy": {"pyserial-asyncio"},
    },
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

    if standard_library_violations:
        integration.add_error(
            "requirements",
            (
                f"Package {req} has dependencies {standard_library_violations} which "
                "are not compatible with the Python standard library"
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
            "dependencies": {"flake8": ">=1.2.3, <4.5.0"}
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
            "dependencies": {
                dep["key"]: dep["required_version"] for dep in item["dependencies"]
            },
        }
    return deptree


def get_requirements(integration: Integration, packages: set[str]) -> set[str]:
    """Return all (recursively) requirements for an integration."""
    deptree = get_pipdeptree()

    all_requirements = set()

    to_check = deque(packages)

    forbidden_package_exceptions = FORBIDDEN_PACKAGE_EXCEPTIONS.get(
        integration.domain, {}
    )
    needs_forbidden_package_exceptions = False

    package_version_check_exceptions = PACKAGE_CHECK_VERSION_RANGE_EXCEPTIONS.get(
        integration.domain, {}
    )
    needs_package_version_check_exception = False

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

        dependencies: dict[str, str] = item["dependencies"]
        package_exceptions = forbidden_package_exceptions.get(package, set())
        for pkg, version in dependencies.items():
            if pkg.startswith("types-") or pkg in FORBIDDEN_PACKAGES:
                reason = FORBIDDEN_PACKAGES.get(pkg, "not be a runtime dependency")
                needs_forbidden_package_exceptions = True
                if pkg in package_exceptions:
                    integration.add_warning(
                        "requirements",
                        f"Package {pkg} should {reason} in {package}",
                    )
                else:
                    integration.add_error(
                        "requirements",
                        f"Package {pkg} should {reason} in {package}",
                    )
            if not check_dependency_version_range(
                integration,
                package,
                pkg,
                version,
                package_version_check_exceptions.get(package, set()),
            ):
                needs_package_version_check_exception = True

        to_check.extend(dependencies)

    if forbidden_package_exceptions and not needs_forbidden_package_exceptions:
        integration.add_error(
            "requirements",
            f"Integration {integration.domain} runtime dependency exceptions "
            "have been resolved, please remove from `FORBIDDEN_PACKAGE_EXCEPTIONS`",
        )
    if package_version_check_exceptions and not needs_package_version_check_exception:
        integration.add_error(
            "requirements",
            f"Integration {integration.domain} version restrictions checks have been "
            "resolved, please remove from `PACKAGE_CHECK_VERSION_RANGE_EXCEPTIONS`",
        )

    return all_requirements


def check_dependency_version_range(
    integration: Integration,
    source: str,
    pkg: str,
    version: str,
    package_exceptions: set[str],
) -> bool:
    """Check requirement version range.

    We want to avoid upper version bounds that are too strict for common packages.
    """
    if (
        version == "Any"
        or (convention := PACKAGE_CHECK_VERSION_RANGE.get(pkg)) is None
        or all(
            _is_dependency_version_range_valid(version_part, convention)
            for version_part in version.split(";", 1)[0].split(",")
        )
    ):
        return True

    if pkg in package_exceptions:
        integration.add_warning(
            "requirements",
            f"Version restrictions for {pkg} are too strict ({version}) in {source}",
        )
    else:
        integration.add_error(
            "requirements",
            f"Version restrictions for {pkg} are too strict ({version}) in {source}",
        )
    return False


def _is_dependency_version_range_valid(version_part: str, convention: str) -> bool:
    version_match = PIP_VERSION_RANGE_SEPARATOR.match(version_part)
    operator = version_match.group(1)
    version = version_match.group(2)

    if operator in (">", ">=", "!="):
        # Lower version binding and version exclusion are fine
        return True

    if convention == "SemVer":
        if operator == "==":
            # Explicit version with wildcard is allowed only on major version
            # e.g. ==1.* is allowed, but ==1.2.* is not
            return version.endswith(".*") and version.count(".") == 1

        awesome = AwesomeVersion(version)
        if operator in ("<", "<="):
            # Upper version binding only allowed on major version
            # e.g. <=3 is allowed, but <=3.1 is not
            return awesome.section(1) == 0 and awesome.section(2) == 0

        if operator == "~=":
            # Compatible release operator is only allowed on major or minor version
            # e.g. ~=1.2 is allowed, but ~=1.2.3 is not
            return awesome.section(2) == 0

    return False


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
