#!/usr/bin/env python3
"""Generate updated constraint and requirements files."""

from __future__ import annotations

import difflib
import importlib
from operator import itemgetter
from pathlib import Path
import pkgutil
import re
import sys
import tomllib
from typing import Any

from homeassistant.util.yaml.loader import load_yaml
from script.hassfest.model import Config, Integration

# Requirements which can't be installed on all systems because they rely on additional
# system packages. Requirements listed in EXCLUDED_REQUIREMENTS_ALL will be commented-out
# in requirements_all.txt and requirements_test_all.txt.
EXCLUDED_REQUIREMENTS_ALL = {
    "atenpdu",  # depends on pysnmp which is not maintained at this time
    "avea",  # depends on bluepy
    "avion",
    "beacontools",
    "beewi-smartclim",  # depends on bluepy
    "bluepy",
    "decora",
    "decora-wifi",
    "evdev",
    "face-recognition",
    "pybluez",
    "pycocotools",
    "pycups",
    "python-gammu",
    "python-lirc",
    "pyuserinput",
    "tensorflow",
    "tf-models-official",
}

# Requirements excluded by EXCLUDED_REQUIREMENTS_ALL which should be included when
# building integration wheels for all architectures.
INCLUDED_REQUIREMENTS_WHEELS = {
    "decora-wifi",
    "evdev",
    "pycups",
    "python-gammu",
    "pyuserinput",
}


# Requirements to exclude or include when running github actions.
# Requirements listed in "exclude" will be commented-out in
# requirements_all_{action}.txt
# Requirements listed in "include" must be listed in EXCLUDED_REQUIREMENTS_CI, and
# will be included in requirements_all_{action}.txt

OVERRIDDEN_REQUIREMENTS_ACTIONS = {
    "pytest": {
        "exclude": set(),
        "include": {"python-gammu"},
        "markers": {},
    },
    "wheels_aarch64": {
        "exclude": set(),
        "include": INCLUDED_REQUIREMENTS_WHEELS,
        "markers": {},
    },
    # Pandas has issues building on armhf, it is expected they
    # will drop the platform in the near future (they consider it
    # "flimsy" on 386). The following packages depend on pandas,
    # so we comment them out.
    "wheels_armhf": {
        "exclude": {"env-canada", "noaa-coops", "pyezviz", "pykrakenapi"},
        "include": INCLUDED_REQUIREMENTS_WHEELS,
        "markers": {},
    },
    "wheels_armv7": {
        "exclude": set(),
        "include": INCLUDED_REQUIREMENTS_WHEELS,
        "markers": {},
    },
    "wheels_amd64": {
        "exclude": set(),
        "include": INCLUDED_REQUIREMENTS_WHEELS,
        "markers": {},
    },
    "wheels_i386": {
        "exclude": set(),
        "include": INCLUDED_REQUIREMENTS_WHEELS,
        "markers": {},
    },
}

IGNORE_PIN = ("colorlog>2.1,<3", "urllib3")

URL_PIN = (
    "https://developers.home-assistant.io/docs/"
    "creating_platform_code_review.html#1-requirements"
)


CONSTRAINT_PATH = (
    Path(__file__).parent.parent / "homeassistant" / "package_constraints.txt"
)
CONSTRAINT_BASE = """
# Constrain pycryptodome to avoid vulnerability
# see https://github.com/home-assistant/core/pull/16238
pycryptodome>=3.6.6

# Constrain httplib2 to protect against GHSA-93xj-8mrv-444m
# https://github.com/advisories/GHSA-93xj-8mrv-444m
httplib2>=0.19.0

# gRPC is an implicit dependency that we want to make explicit so we manage
# upgrades intentionally. It is a large package to build from source and we
# want to ensure we have wheels built.
grpcio==1.71.0
grpcio-status==1.71.0
grpcio-reflection==1.71.0

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

# httpx requires httpcore, and httpcore requires anyio and h11, but the version constraints on
# these requirements are quite loose. As the entire stack has some outstanding issues, and
# even newer versions seem to introduce new issues, it's useful for us to pin all these
# requirements so we can directly link HA versions to these library versions.
anyio==4.9.0
h11==0.14.0
httpcore==1.0.7

# Ensure we have a hyperframe version that works in Python 3.10
# 5.2.0 fixed a collections abc deprecation
hyperframe>=5.2.0

# Ensure we run compatible with musllinux build env
numpy==2.2.2
pandas~=2.2.3

# Constrain multidict to avoid typing issues
# https://github.com/home-assistant/core/pull/67046
multidict>=6.0.2

# Version 2.0 added typing, prevent accidental fallbacks
backoff>=2.0

# ensure pydantic version does not float since it might have breaking changes
pydantic==2.11.3

# Required for Python 3.12.4 compatibility (#119223).
mashumaro>=3.13.1

# Breaks asyncio
# https://github.com/pubnub/python/issues/130
pubnub!=6.4.0

# Package's __init__.pyi stub has invalid syntax and breaks mypy
# https://github.com/dahlia/iso4217/issues/16
iso4217!=1.10.20220401

# pyOpenSSL 24.0.0 or later required to avoid import errors when
# cryptography 42.0.0 is installed with botocore
pyOpenSSL>=24.0.0

# protobuf must be in package constraints for the wheel
# builder to build binary wheels
protobuf==5.29.2

# faust-cchardet: Ensure we have a version we can build wheels
# 2.1.18 is the first version that works with our wheel builder
faust-cchardet>=2.1.18

# websockets 13.1 is the first version to fully support the new
# asyncio implementation. The legacy implementation is now
# deprecated as of websockets 14.0.
# https://websockets.readthedocs.io/en/13.0.1/howto/upgrade.html#missing-features
# https://websockets.readthedocs.io/en/stable/howto/upgrade.html
websockets>=13.1

# pysnmplib is no longer maintained and does not work with newer
# python
pysnmplib==1000000000.0.0

# The get-mac package has been replaced with getmac. Installing get-mac alongside getmac
# breaks getmac due to them both sharing the same python package name inside 'getmac'.
get-mac==1000000000.0.0

# Poetry is a build dependency. Installing it as a runtime dependency almost
# always indicates an issue with library requirements.
poetry==1000000000.0.0

# We want to skip the binary wheels for the 'charset-normalizer' packages.
# They are build with mypyc, but causes issues with our wheel builder.
# In order to do so, we need to constrain the version.
charset-normalizer==3.4.0

# dacite: Ensure we have a version that is able to handle type unions for
# NAM, Brother, and GIOS.
dacite>=1.7.0

# chacha20poly1305-reuseable==0.12.x is incompatible with cryptography==43.0.x
chacha20poly1305-reuseable>=0.13.0

# pycountry<23.12.11 imports setuptools at run time
# https://github.com/pycountry/pycountry/blob/ea69bab36f00df58624a0e490fdad4ccdc14268b/HISTORY.txt#L39
pycountry>=23.12.11

# scapy==2.6.0 causes CI failures due to a race condition
scapy>=2.6.1

# tuf isn't updated to deal with breaking changes in securesystemslib==1.0.
# Only tuf>=4 includes a constraint to <1.0.
# https://github.com/theupdateframework/python-tuf/releases/tag/v4.0.0
tuf>=4.0.0

# https://github.com/jd/tenacity/issues/471
tenacity!=8.4.0

# 5.0.0 breaks Timeout as a context manager
# TypeError: 'Timeout' object does not support the context manager protocol
async-timeout==4.0.3

# aiofiles keeps getting downgraded by custom components
# causing newer methods to not be available and breaking
# some integrations at startup
# https://github.com/home-assistant/core/issues/127529
# https://github.com/home-assistant/core/issues/122508
# https://github.com/home-assistant/core/issues/118004
aiofiles>=24.1.0

# multidict < 6.4.0 has memory leaks
# https://github.com/aio-libs/multidict/issues/1134
# https://github.com/aio-libs/multidict/issues/1131
multidict>=6.4.2

# rpds-py > 0.25.0 requires cargo 1.84.0
# Stable Alpine current only ships cargo 1.83.0
# No wheels upstream available for armhf & armv7
rpds-py==0.24.0
"""

GENERATED_MESSAGE = (
    f"# Automatically generated by {Path(__file__).name}, do not edit\n\n"
)

IGNORE_PRE_COMMIT_HOOK_ID = (
    "check-executables-have-shebangs",
    "check-json",
    "no-commit-to-branch",
    "prettier",
    "python-typing-update",
    "ruff-format",  # it's just ruff
)

PACKAGE_REGEX = re.compile(r"^(?:--.+\s)?([-_\.\w\d]+).*==.+$")


def has_tests(module: str) -> bool:
    """Test if a module has tests.

    Module format: homeassistant.components.hue
    Test if exists: tests/components/hue/__init__.py
    """
    path = (
        Path(module.replace(".", "/").replace("homeassistant", "tests", 1))
        / "__init__.py"
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
    data = tomllib.loads(Path("pyproject.toml").read_text())
    dependencies: list[str] = data["project"]["dependencies"]
    return dependencies


def gather_recursive_requirements(
    domain: str, seen: set[str] | None = None
) -> set[str]:
    """Recursively gather requirements from a module."""
    if seen is None:
        seen = set()

    seen.add(domain)
    integration = Integration(
        Path(f"homeassistant/components/{domain}"), _get_hassfest_config()
    )
    integration.load_manifest()
    reqs = {x for x in integration.requirements if x not in CONSTRAINT_BASE}
    for dep_domain in integration.dependencies:
        reqs.update(gather_recursive_requirements(dep_domain, seen))
    return reqs


def _normalize_package_name(package_name: str) -> str:
    """Normalize a package name."""
    # pipdeptree needs lowercase and dash instead of underscore or period as separator
    return package_name.lower().replace("_", "-").replace(".", "-")


def normalize_package_name(requirement: str) -> str:
    """Return a normalized package name from a requirement string."""
    # This function is also used in hassfest.
    match = PACKAGE_REGEX.search(requirement)
    if not match:
        return ""

    # pipdeptree needs lowercase and dash instead of underscore or period as separator
    return _normalize_package_name(match.group(1))


def comment_requirement(req: str) -> bool:
    """Comment out requirement. Some don't install on all systems."""
    return normalize_package_name(req) in EXCLUDED_REQUIREMENTS_ALL


def process_action_requirement(req: str, action: str) -> str:
    """Process requirement for a specific github action."""
    normalized_package_name = normalize_package_name(req)
    if normalized_package_name in OVERRIDDEN_REQUIREMENTS_ACTIONS[action]["exclude"]:
        return f"# {req}"
    if normalized_package_name in OVERRIDDEN_REQUIREMENTS_ACTIONS[action]["include"]:
        return req
    if normalized_package_name in EXCLUDED_REQUIREMENTS_ALL:
        return f"# {req}"
    if markers := OVERRIDDEN_REQUIREMENTS_ACTIONS[action]["markers"].get(
        normalized_package_name, None
    ):
        return f"{req};{markers}"
    return req


def gather_modules() -> dict[str, list[str]] | None:
    """Collect the information."""
    reqs: dict[str, list[str]] = {}

    errors: list[str] = []

    gather_requirements_from_manifests(errors, reqs)
    gather_requirements_from_modules(errors, reqs)

    for value in reqs.values():
        value = sorted(value, key=lambda name: (len(name.split(".")), name))

    if errors:
        print("******* ERROR")
        print("Errors while importing: ", ", ".join(errors))
        return None

    return reqs


def gather_requirements_from_manifests(
    errors: list[str], reqs: dict[str, list[str]]
) -> None:
    """Gather all of the requirements from manifests."""
    config = _get_hassfest_config()
    integrations = Integration.load_dir(config.core_integrations_path, config)
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
    for pkg, requirements in sorted(reqs.items(), key=itemgetter(0)):
        output.extend(f"\n# {req}" for req in sorted(requirements))

        if comment_requirement(pkg):
            output.append(f"\n# {pkg}\n")
        else:
            output.append(f"\n{pkg}\n")
    return "".join(output)


def generate_action_requirements_list(reqs: dict[str, list[str]], action: str) -> str:
    """Generate a pip file based on requirements."""
    output = []
    for pkg, requirements in sorted(reqs.items(), key=itemgetter(0)):
        output.extend(f"\n# {req}" for req in sorted(requirements))
        processed_pkg = process_action_requirement(pkg, action)
        output.append(f"\n{processed_pkg}\n")
    return "".join(output)


def requirements_output() -> str:
    """Generate output for requirements."""
    output = [
        GENERATED_MESSAGE,
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
        GENERATED_MESSAGE,
        "-r requirements.txt\n",
    ]
    output.append(generate_requirements_list(reqs))

    return "".join(output)


def requirements_all_action_output(reqs: dict[str, list[str]], action: str) -> str:
    """Generate output for requirements_all_{action}."""
    output = [
        f"# Home Assistant Core, full dependency set for {action}\n",
        GENERATED_MESSAGE,
        "-r requirements.txt\n",
    ]
    output.append(generate_action_requirements_list(reqs, action))

    return "".join(output)


def requirements_test_all_output(reqs: dict[str, list[str]]) -> str:
    """Generate output for test_requirements."""
    output = [
        "# Home Assistant tests, full dependency set\n",
        GENERATED_MESSAGE,
        "-r requirements_test.txt\n",
    ]

    filtered = {
        requirement: modules
        for requirement, modules in reqs.items()
        if any(
            # Always install requirements that are not part of integrations
            not mdl.startswith("homeassistant.components.")
            or
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
        GENERATED_MESSAGE
        + "\n".join(
            [
                *sorted(
                    {
                        *core_requirements(),
                        *gather_recursive_requirements("default_config"),
                        *gather_recursive_requirements("mqtt"),
                    },
                    key=str.lower,
                ),
                "",
            ]
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


def main(validate: bool, ci: bool) -> int:
    """Run the script."""
    if not Path("requirements_all.txt").is_file():
        print("Run this from HA root dir")
        return 1

    data = gather_modules()

    if data is None:
        return 1

    reqs_file = requirements_output()
    reqs_all_file = requirements_all_output(data)
    reqs_all_action_files = {
        action: requirements_all_action_output(data, action)
        for action in OVERRIDDEN_REQUIREMENTS_ACTIONS
    }
    reqs_test_all_file = requirements_test_all_output(data)
    # Always calling requirements_pre_commit_output is intentional to ensure
    # the code is called by the pre-commit hooks.
    reqs_pre_commit_file = requirements_pre_commit_output()
    constraints = gather_constraints()

    files = [
        ("requirements.txt", reqs_file),
        ("requirements_all.txt", reqs_all_file),
        ("requirements_test_pre_commit.txt", reqs_pre_commit_file),
        ("requirements_test_all.txt", reqs_test_all_file),
        ("homeassistant/package_constraints.txt", constraints),
    ]
    if ci:
        files.extend(
            (f"requirements_all_{action}.txt", reqs_all_file)
            for action, reqs_all_file in reqs_all_action_files.items()
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


def _get_hassfest_config() -> Config:
    """Get hassfest config."""
    return Config(
        root=Path().absolute(),
        specific_integrations=None,
        action="validate",
        requirements=True,
    )


if __name__ == "__main__":
    _VAL = sys.argv[-1] == "validate"
    _CI = sys.argv[-1] == "ci"
    sys.exit(main(_VAL, _CI))
