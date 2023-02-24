#!/usr/bin/env python3
"""Generate updated constraint and requirements files."""
from __future__ import annotations

import difflib
import importlib
import os
from pathlib import Path
import pkgutil
import re
import sys
from typing import Any

from homeassistant.util.yaml.loader import load_yaml
from script.hassfest.model import Integration

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

COMMENT_REQUIREMENTS = (
    "Adafruit_BBIO",
    "avea",  # depends on bluepy
    "avion",
    "beacontools",
    "beewi_smartclim",  # depends on bluepy
    "bluepy",
    "decora",
    "decora_wifi",
    "evdev",
    "face_recognition",
    "opencv-python-headless",
    "pybluez",
    "pycups",
    "python-eq3bt",
    "python-gammu",
    "python-lirc",
    "pyuserinput",
    "tensorflow",
    "tf-models-official",
)

COMMENT_REQUIREMENTS_NORMALIZED = {
    commented.lower().replace("_", "-") for commented in COMMENT_REQUIREMENTS
}

IGNORE_PIN = ("colorlog>2.1,<3", "urllib3")

URL_PIN = (
    "https://developers.home-assistant.io/docs/"
    "creating_platform_code_review.html#1-requirements"
)


CONSTRAINT_PATH = os.path.join(
    os.path.dirname(__file__), "../homeassistant/package_constraints.txt"
)
CONSTRAINT_BASE = """
# Constrain pycryptodome to avoid vulnerability
# see https://github.com/home-assistant/core/pull/16238
pycryptodome>=3.6.6

# Constrain urllib3 to ensure we deal with CVE-2020-26137 and CVE-2021-33503
urllib3>=1.26.5

# Constrain httplib2 to protect against GHSA-93xj-8mrv-444m
# https://github.com/advisories/GHSA-93xj-8mrv-444m
httplib2>=0.19.0

# gRPC is an implicit dependency that we want to make explicit so we manage
# upgrades intentionally. It is a large package to build from source and we
# want to ensure we have wheels built.
grpcio==1.51.1
grpcio-status==1.51.1
grpcio-reflection==1.51.1

# libcst >=0.4.0 requires a newer Rust than we currently have available,
# thus our wheels builds fail. This pins it to the last working version,
# which at this point satisfies our needs.
libcst==0.3.23

# This is a old unmaintained library and is replaced with pycryptodome
pycrypto==1000000000.0.0

# This is a old unmaintained library and is replaced with faust-cchardet
cchardet==1000000000.0.0

# To remove reliance on typing
btlewrap>=0.0.10

# This overrides a built-in Python package
enum34==1000000000.0.0
typing==1000000000.0.0
uuid==1000000000.0.0

# regex causes segfault with version 2021.8.27
# https://bitbucket.org/mrabarnett/mrab-regex/issues/421/2021827-results-in-fatal-python-error
# This is fixed in 2021.8.28
regex==2021.8.28

# httpx requires httpcore, and httpcore requires anyio and h11, but the version constraints on
# these requirements are quite loose. As the entire stack has some outstanding issues, and
# even newer versions seem to introduce new issues, it's useful for us to pin all these
# requirements so we can directly link HA versions to these library versions.
anyio==3.6.2
h11==0.14.0
httpcore==0.16.3

# Ensure we have a hyperframe version that works in Python 3.10
# 5.2.0 fixed a collections abc deprecation
hyperframe>=5.2.0

# Ensure we run compatible with musllinux build env
numpy==1.23.2

# Prevent dependency conflicts between sisyphus-control and aioambient
# until upper bounds for sisyphus-control have been updated
# https://github.com/jkeljo/sisyphus-control/issues/6
python-engineio>=3.13.1,<4.0
python-socketio>=4.6.0,<5.0

# Constrain multidict to avoid typing issues
# https://github.com/home-assistant/core/pull/67046
multidict>=6.0.2

# Required for compatibility with point integration - ensure_active_token
# https://github.com/home-assistant/core/pull/68176
authlib<1.0

# Version 2.0 added typing, prevent accidental fallbacks
backoff>=2.0

# Breaking change in version
# https://github.com/samuelcolvin/pydantic/issues/4092
pydantic!=1.9.1

# Breaks asyncio
# https://github.com/pubnub/python/issues/130
pubnub!=6.4.0

# Package's __init__.pyi stub has invalid syntax and breaks mypy
# https://github.com/dahlia/iso4217/issues/16
iso4217!=1.10.20220401

# Pandas 1.4.4 has issues with wheels om armhf + Py3.10
pandas==1.4.3

# Matplotlib 3.6.2 has issues building wheels on armhf/armv7
# We need at least >=2.1.0 (tensorflow integration -> pycocotools)
matplotlib==3.6.1

# pyOpenSSL 23.0.0 or later required to avoid import errors when
# cryptography 39.0.0 is installed with botocore
pyOpenSSL>=23.0.0

# uamqp newer versions we currently can't build for armv7/armhf
# Limit this to Python 3.10, to not block Python 3.11 dev for now
uamqp==1.6.0;python_version<'3.11'

# faust-cchardet: Ensure we have a version we can build wheels
# 2.1.18 is the first version that works with our wheel builder
faust-cchardet>=2.1.18
"""

IGNORE_PRE_COMMIT_HOOK_ID = (
    "check-executables-have-shebangs",
    "check-json",
    "no-commit-to-branch",
    "prettier",
    "python-typing-update",
)

PACKAGE_REGEX = re.compile(r"^(?:--.+\s)?([-_\.\w\d]+).*==.+$")


def has_tests(module: str) -> bool:
    """Test if a module has tests.

    Module format: homeassistant.components.hue
    Test if exists: tests/components/hue/__init__.py
    """
    path = (
        Path(module.replace(".", "/").replace("homeassistant", "tests")) / "__init__.py"
    )
    return path.exists()


def explore_module(package: str, explore_children: bool) -> list[str]:
    """Explore the modules."""
    module = importlib.import_module(package)

    found: list[str] = []

    if not hasattr(module, "__path__"):
        return found

    for _, name, _ in pkgutil.iter_modules(module.__path__, f"{package}."):
        found.append(name)

        if explore_children:
            found.extend(explore_module(name, False))

    return found


def core_requirements() -> list[str]:
    """Gather core requirements out of pyproject.toml."""
    with open("pyproject.toml", "rb") as fp:
        data = tomllib.load(fp)
    dependencies: list[str] = data["project"]["dependencies"]
    return dependencies


def gather_recursive_requirements(
    domain: str, seen: set[str] | None = None
) -> set[str]:
    """Recursively gather requirements from a module."""
    if seen is None:
        seen = set()

    seen.add(domain)
    integration = Integration(Path(f"homeassistant/components/{domain}"))
    integration.load_manifest()
    reqs = {x for x in integration.requirements if x not in CONSTRAINT_BASE}
    for dep_domain in integration.dependencies:
        reqs.update(gather_recursive_requirements(dep_domain, seen))
    return reqs


def normalize_package_name(requirement: str) -> str:
    """Return a normalized package name from a requirement string."""
    # This function is also used in hassfest.
    match = PACKAGE_REGEX.search(requirement)
    if not match:
        return ""

    # pipdeptree needs lowercase and dash instead of underscore as separator
    package = match.group(1).lower().replace("_", "-")

    return package


def comment_requirement(req: str) -> bool:
    """Comment out requirement. Some don't install on all systems."""
    return any(
        normalize_package_name(req) == ign for ign in COMMENT_REQUIREMENTS_NORMALIZED
    )


def gather_modules() -> dict[str, list[str]] | None:
    """Collect the information."""
    reqs: dict[str, list[str]] = {}

    errors: list[str] = []

    gather_requirements_from_manifests(errors, reqs)
    gather_requirements_from_modules(errors, reqs)

    for key in reqs:
        reqs[key] = sorted(reqs[key], key=lambda name: (len(name.split(".")), name))

    if errors:
        print("******* ERROR")
        print("Errors while importing: ", ", ".join(errors))
        return None

    return reqs


def gather_requirements_from_manifests(
    errors: list[str], reqs: dict[str, list[str]]
) -> None:
    """Gather all of the requirements from manifests."""
    integrations = Integration.load_dir(Path("homeassistant/components"))
    for domain in sorted(integrations):
        integration = integrations[domain]

        if integration.disabled:
            continue

        process_requirements(
            errors, integration.requirements, f"homeassistant.components.{domain}", reqs
        )


def gather_requirements_from_modules(
    errors: list[str], reqs: dict[str, list[str]]
) -> None:
    """Collect the requirements from the modules directly."""
    for package in sorted(
        explore_module("homeassistant.scripts", True)
        + explore_module("homeassistant.auth", True)
    ):
        try:
            module = importlib.import_module(package)
        except ImportError as err:
            print(f"{package.replace('.', '/')}.py: {err}")
            errors.append(package)
            continue

        if getattr(module, "REQUIREMENTS", None):
            process_requirements(errors, module.REQUIREMENTS, package, reqs)


def process_requirements(
    errors: list[str],
    module_requirements: list[str],
    package: str,
    reqs: dict[str, list[str]],
) -> None:
    """Process all of the requirements."""
    for req in module_requirements:
        if "://" in req:
            errors.append(f"{package}[Only pypi dependencies are allowed: {req}]")
        if req.partition("==")[1] == "" and req not in IGNORE_PIN:
            errors.append(f"{package}[Please pin requirement {req}, see {URL_PIN}]")
        reqs.setdefault(req, []).append(package)


def generate_requirements_list(reqs: dict[str, list[str]]) -> str:
    """Generate a pip file based on requirements."""
    output = []
    for pkg, requirements in sorted(reqs.items(), key=lambda item: item[0]):
        for req in sorted(requirements):
            output.append(f"\n# {req}")

        if comment_requirement(pkg):
            output.append(f"\n# {pkg}\n")
        else:
            output.append(f"\n{pkg}\n")
    return "".join(output)


def requirements_output() -> str:
    """Generate output for requirements."""
    output = [
        "-c homeassistant/package_constraints.txt\n",
        "\n",
        "# Home Assistant Core\n",
    ]
    output.append("\n".join(core_requirements()))
    output.append("\n")

    return "".join(output)


def requirements_all_output(reqs: dict[str, list[str]]) -> str:
    """Generate output for requirements_all."""
    output = [
        "# Home Assistant Core, full dependency set\n",
        "-r requirements.txt\n",
    ]
    output.append(generate_requirements_list(reqs))

    return "".join(output)


def requirements_test_all_output(reqs: dict[str, list[str]]) -> str:
    """Generate output for test_requirements."""
    output = [
        "# Home Assistant tests, full dependency set\n",
        f"# Automatically generated by {Path(__file__).name}, do not edit\n",
        "\n",
        "-r requirements_test.txt\n",
    ]

    filtered = {
        requirement: modules
        for requirement, modules in reqs.items()
        if any(
            # Always install requirements that are not part of integrations
            not mdl.startswith("homeassistant.components.") or
            # Install tests for integrations that have tests
            has_tests(mdl)
            for mdl in modules
        )
    }
    output.append(generate_requirements_list(filtered))

    return "".join(output)


def requirements_pre_commit_output() -> str:
    """Generate output for pre-commit dependencies."""
    source = ".pre-commit-config.yaml"
    pre_commit_conf: dict[str, list[dict[str, Any]]]
    pre_commit_conf = load_yaml(source)  # type: ignore[assignment]
    reqs: list[str] = []
    hook: dict[str, Any]
    for repo in (x for x in pre_commit_conf["repos"] if x.get("rev")):
        rev: str = repo["rev"]
        for hook in repo["hooks"]:
            if hook["id"] not in IGNORE_PRE_COMMIT_HOOK_ID:
                reqs.append(f"{hook['id']}=={rev.lstrip('v')}")
                reqs.extend(x for x in hook.get("additional_dependencies", ()))
    output = [
        f"# Automatically generated "
        f"from {source} by {Path(__file__).name}, do not edit",
        "",
    ]
    output.extend(sorted(reqs))
    return "\n".join(output) + "\n"


def gather_constraints() -> str:
    """Construct output for constraint file."""
    return (
        "\n".join(
            sorted(
                {
                    *core_requirements(),
                    *gather_recursive_requirements("default_config"),
                    *gather_recursive_requirements("mqtt"),
                }
            )
            + [""]
        )
        + CONSTRAINT_BASE
    )


def diff_file(filename: str, content: str) -> list[str]:
    """Diff a file."""
    return list(
        difflib.context_diff(
            [f"{line}\n" for line in Path(filename).read_text().split("\n")],
            [f"{line}\n" for line in content.split("\n")],
            filename,
            "generated",
        )
    )


def main(validate: bool) -> int:
    """Run the script."""
    if not os.path.isfile("requirements_all.txt"):
        print("Run this from HA root dir")
        return 1

    data = gather_modules()

    if data is None:
        return 1

    reqs_file = requirements_output()
    reqs_all_file = requirements_all_output(data)
    reqs_test_all_file = requirements_test_all_output(data)
    reqs_pre_commit_file = requirements_pre_commit_output()
    constraints = gather_constraints()

    files = (
        ("requirements.txt", reqs_file),
        ("requirements_all.txt", reqs_all_file),
        ("requirements_test_pre_commit.txt", reqs_pre_commit_file),
        ("requirements_test_all.txt", reqs_test_all_file),
        ("homeassistant/package_constraints.txt", constraints),
    )

    if validate:
        errors = []

        for filename, content in files:
            diff = diff_file(filename, content)
            if diff:
                errors.append("".join(diff))

        if errors:
            print("ERROR - FOUND THE FOLLOWING DIFFERENCES")
            print()
            print()
            print("\n\n".join(errors))
            print()
            print("Please run python3 -m script.gen_requirements_all")
            return 1

        return 0

    for filename, content in files:
        Path(filename).write_text(content)

    return 0


if __name__ == "__main__":
    _VAL = sys.argv[-1] == "validate"
    sys.exit(main(_VAL))
