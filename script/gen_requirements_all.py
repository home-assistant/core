#!/usr/bin/env python3
"""Generate updated constraint and requirements files."""

import difflib
import importlib
import json
from operator import itemgetter
from pathlib import Path
import pkgutil
import sys
import tomllib
from typing import Any

from hassfest.model import Config, Integration
from hassfest.requirements_util import EXCLUDED_REQUIREMENTS_ALL, normalize_package_name
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from homeassistant.util.yaml.loader import load_yaml

# Requirements excluded by EXCLUDED_REQUIREMENTS_ALL which should be included when
# building integration wheels for all architectures.
INCLUDED_REQUIREMENTS_WHEELS = {
    "evdev",
}


# Requirements to exclude or include when running github actions.
# Requirements listed in "exclude" will be commented-out in
# requirements_all_{action}.txt
# Requirements listed in "include" must be listed in EXCLUDED_REQUIREMENTS_CI, and
# will be included in requirements_all_{action}.txt

OVERRIDDEN_REQUIREMENTS_ACTIONS = {
    "wheels_aarch64": {
        "exclude": set(),
        "include": INCLUDED_REQUIREMENTS_WHEELS,
        "markers": {},
    },
    "wheels_amd64": {
        "exclude": set(),
        "include": INCLUDED_REQUIREMENTS_WHEELS,
        "markers": {},
    },
}

URL_PIN = (
    "https://contributors.home-assistant.io/core/integrations/manifest/#requirements"
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
grpcio==1.83.1
grpcio-status==1.83.1
grpcio-reflection==1.83.1

# boto3 and botocore are shared requirements of multiple integrations,
# with botocore also being a transitive dependency of aiobotocore, which
# only accepts a narrow botocore version range. Pin them together so a
# runtime requirement install cannot pull in a botocore version that is
# incompatible with aiobotocore.
# see https://github.com/home-assistant/core/issues/167399
boto3==1.42.97
botocore==1.42.97

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

# httpx2 requires httpcore2 and anyio, while httpcore2 requires h11. The
# version constraints on anyio and h11 are quite loose. Pin them so we can
# directly link HA versions to these library versions.
anyio==4.15.1
h11==0.16.0

# Many libraries still depend on httpx/httpcore. Those imports are aliased to
# httpx2/httpcore2 at runtime, but pin the installed packages so a dependency
# cannot pull in an untested httpx version alongside httpx2.
httpcore==1.0.9
httpx==0.28.1

# Ensure we run compatible with musllinux build env
numpy==2.3.2
pandas==2.3.3

# Constrain multidict to avoid typing issues
# https://github.com/home-assistant/core/pull/67046
multidict>=6.0.2

# Brotli 1.2.1 fixes CVE
Brotli>=1.2.1

# ensure pydantic version does not float since it might have breaking changes
pydantic==2.14.1

# Required for Python 3.14.0 compatibility (#119223).
mashumaro>=3.17.0

# Breaks asyncio
# https://github.com/pubnub/python/issues/130
pubnub!=6.4.0

# Package's __init__.pyi stub has invalid syntax and breaks mypy
# https://github.com/dahlia/iso4217/issues/16
iso4217!=1.10.20220401

# protobuf must be in package constraints for the wheel
# builder to build binary wheels
protobuf==7.36.0

# faust-cchardet: Ensure we have a version we can build wheels
# 2.1.18 is the first version that works with our wheel builder
faust-cchardet>=2.1.18

# Prevent accidental fallbacks
websockets>=15.0.1

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
charset-normalizer==3.4.3

# dacite: Ensure we have a version that is able to handle type unions for
# NAM, Brother, and GIOS.
dacite>=1.7.0

# decorator 5.3.0 dropped license metadata required by script/licenses.py.
# Pin to 5.2.1 until license metadata is restored.
decorator==5.2.1

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

# Constraint num2words to 0.5.14 as 0.5.15 and 0.5.16 were removed from PyPI
num2words==0.5.14

# pymodbus does not follow SemVer, and it keeps getting
# downgraded or upgraded by custom components
# This ensures all use the same version
pymodbus==3.13.1

# Pin pytest-rerunfailures to prevent accidental breaks
pytest-rerunfailures==16.0.1

# Fixes detected blocking call to load_default_certs https://github.com/home-assistant/core/issues/157475
aiomqtt>=2.5.0

# aiofile 3.10.0 crashes on import due to KeyError on package metadata
# https://github.com/mosquito/aiofile/pull/106
aiofile>=3.10.1
# caio 0.12.2 includes 'tests' package in wheel
# Fixed upstream in https://github.com/mosquito/caio/pull/75
# but not released yet. Pin here to prevent hassfest failure.
# Update manually once next release is available.
caio<0.12.3

# auth0-python v5.0 is a major rewrite with breaking changes
# used by sharkiq==1.5.0
# https://github.com/auth0/auth0-python/releases/tag/5.0.0
auth0-python<5.0

# backoff and python-backoff share the same package name
# pin versions which are mostly compatible to each other
backoff==2.2.1
python-backoff<2.4.0

# bitstring 5.0.0 removed ConstBitStream, which pysml (used by edl21) still imports
# https://github.com/home-assistant/core/issues/185883
# https://codeberg.org/obi/pysml/issues/33
# Remove once pysml supports bitstring>=5
bitstring<5

# graphql-core 3.3 removed graphql_input_types, which apischema 0.19.0
# (used by aioaseko) still imports
# https://github.com/home-assistant/core/issues/184918
graphql-core<3.3

# pycares 5.1.0/5.2.0 bundle c-ares 1.34.8, which can break DNS
# https://github.com/home-assistant/core/issues/185645
pycares>=5.2.1

# pypasser 1.0.0 removed reCaptchaV3, which Tami4EdgeAPI imports
pypasser<1.0.0

# Pin dependencies with '.pth' files to exact versions, only update manually!
# https://github.com/Azure/azure-kusto-python/ -> '.pth' files removed with >=5.0.5
# https://github.com/xolox/python-coloredlogs -> unmaintained
# https://github.com/pypa/setuptools
azure-kusto-data==4.5.1
azure-kusto-ingest==4.5.1
coloredlogs==15.0.1
setuptools==84.0.0

# Pin cffi to 2.0.0 to avoid version mismatch with the pre-baked _cffi_backend in the base image.
# https://github.com/home-assistant/core/issues/175832
cffi==2.0.0
"""

GENERATED_MESSAGE = (
    f"# Automatically generated by {Path(__file__).name}, do not edit\n\n"
)

PYTEST_PACKAGE_PATH = Path("packages/pytest-home-assistant/pyproject.toml")

MAP_HOOK_ID_TO_PACKAGE = {
    "ruff-check": "ruff",
}

IGNORE_PRE_COMMIT_HOOK_ID = (
    "check-executables-have-shebangs",
    "check-json",
    "no-commit-to-branch",
    "prettier",
    "ruff-format",  # it's just ruff
)


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

    if not errors:
        reqs = merge_requirement_extras(errors, reqs)

    if errors:
        print("******* ERROR")
        print("Errors while importing: ", ", ".join(errors))
        return None

    return reqs


def merge_requirement_extras(
    errors: list[str], reqs: dict[str, list[str]]
) -> dict[str, list[str]]:
    """Merge the requirements of a package into one requirement."""
    grouped: dict[str, list[str]] = {}
    for req in reqs:
        grouped.setdefault(canonicalize_name(Requirement(req).name), []).append(req)

    merged: dict[str, list[str]] = {}
    for name, group in grouped.items():
        if len(group) == 1:
            merged[group[0]] = reqs[group[0]]
            continue
        requirements = [Requirement(req) for req in group]
        if len({(str(req.specifier), str(req.marker)) for req in requirements}) > 1:
            conflicts = ", ".join(
                f"{req} ({', '.join(sorted(reqs[req]))})" for req in sorted(group)
            )
            errors.append(f"{name}[Conflicting requirements: {conflicts}]")
            continue
        requirement = requirements[0]
        for other in requirements[1:]:
            requirement.extras |= other.extras
        merged[str(requirement)] = sorted(
            {package for req in group for package in reqs[req]}
        )
    return merged


def gather_entity_platform_requirements() -> set[str]:
    """Gather all of the requirements from manifests for entity platforms."""
    config = _get_hassfest_config()
    integrations = Integration.load_dir(config.core_integrations_path, config)
    reqs = set()
    for domain in sorted(integrations):
        integration = integrations[domain]

        if integration.disabled:
            continue

        if integration.integration_type != "entity":
            continue

        reqs.update(gather_recursive_requirements(integration.domain))
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
        if req.partition("==")[1] == "":
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

    requirements = set()
    requirements.update(core_requirements())
    requirements.update(gather_entity_platform_requirements())

    output.append("\n".join(sorted(requirements, key=lambda key: key.lower())))
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
                pkg = MAP_HOOK_ID_TO_PACKAGE.get(hook["id"]) or hook["id"]
                reqs.append(f"{pkg}=={rev.lstrip('v')}")
                reqs.extend(x for x in hook.get("additional_dependencies", ()))
    output = [
        f"# Automatically generated "
        f"from {source} by {Path(__file__).name}, do not edit",
        "",
    ]
    output.extend(sorted(reqs))
    return "\n".join(output) + "\n"


def pytest_package_output(reqs: dict[str, list[str]]) -> str:
    """Keep pytest helper dependencies aligned with Core and test requirements."""
    test_requirements = [
        line
        for line in Path("requirements_test.txt").read_text().splitlines()
        if line and not line.startswith(("#", "-"))
    ]
    versions = {}
    for value in [*reqs, *core_requirements(), *test_requirements]:
        requirement = Requirement(value)
        versions[canonicalize_name(requirement.name)] = requirement.specifier
    content = PYTEST_PACKAGE_PATH.read_text()
    project = tomllib.loads(content)["project"]
    dependencies = [
        *project["dependencies"],
        *(
            dependency
            for extra in project["optional-dependencies"].values()
            for dependency in extra
        ),
    ]
    for dependency in dependencies:
        requirement = Requirement(dependency)
        name = canonicalize_name(requirement.name)
        if name == "homeassistant":
            # The matching Home Assistant version is set when publishing.
            continue
        requirement.specifier = versions[name]
        content = content.replace(json.dumps(dependency), json.dumps(str(requirement)))
    return content


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
    # Always calling requirements_pre_commit_output is intentional to ensure
    # the code is called by the pre-commit hooks.
    reqs_pre_commit_file = requirements_pre_commit_output()
    constraints = gather_constraints()

    files = [
        ("requirements.txt", reqs_file),
        ("requirements_all.txt", reqs_all_file),
        ("requirements_test_pre_commit.txt", reqs_pre_commit_file),
        ("homeassistant/package_constraints.txt", constraints),
        (str(PYTEST_PACKAGE_PATH), pytest_package_output(data)),
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
