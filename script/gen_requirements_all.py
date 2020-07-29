#!/usr/bin/env python3
"""Generate an updated requirements_all.txt."""
import difflib
import importlib
import os
from pathlib import Path
import pkgutil
import re
import sys

from script.hassfest.model import Integration

from homeassistant.util.yaml.loader import load_yaml

COMMENT_REQUIREMENTS = (
    "Adafruit_BBIO",
    "Adafruit-DHT",
    "avion",
    "beacontools",
    "blinkt",
    "bluepy",
    "bme680",
    "credstash",
    "decora",
    "envirophat",
    "evdev",
    "face_recognition",
    "i2csense",
    "opencv-python-headless",
    "py_noaa",
    "pybluez",
    "pycups",
    "PySwitchbot",
    "pySwitchmate",
    "python-eq3bt",
    "python-gammu",
    "python-lirc",
    "pyuserinput",
    "raspihats",
    "rpi-rf",
    "RPi.GPIO",
    "smbus-cffi",
    "tensorflow",
    "VL53L1X2",
)

IGNORE_PIN = ("colorlog>2.1,<3", "keyring>=9.3,<10.0", "urllib3")

URL_PIN = (
    "https://developers.home-assistant.io/docs/"
    "creating_platform_code_review.html#1-requirements"
)


CONSTRAINT_PATH = os.path.join(
    os.path.dirname(__file__), "../homeassistant/package_constraints.txt"
)
CONSTRAINT_BASE = """
pycryptodome>=3.6.6

# Constrain urllib3 to ensure we deal with CVE-2019-11236 & CVE-2019-11324
urllib3>=1.24.3

# Constrain httplib2 to protect against CVE-2020-11078
httplib2>=0.18.0

# Not needed for our supported Python versions
enum34==1000000000.0.0

# This is a old unmaintained library and is replaced with pycryptodome
pycrypto==1000000000.0.0
"""

IGNORE_PRE_COMMIT_HOOK_ID = (
    "check-executables-have-shebangs",
    "check-json",
    "no-commit-to-branch",
    "prettier",
)


def has_tests(module: str):
    """Test if a module has tests.

    Module format: homeassistant.components.hue
    Test if exists: tests/components/hue
    """
    path = Path(module.replace(".", "/").replace("homeassistant", "tests"))
    if not path.exists():
        return False

    if not path.is_dir():
        return True

    # Dev environments might have stale directories around
    # from removed tests. Check for that.
    content = [f.name for f in path.glob("*")]

    # Directories need to contain more than `__pycache__`
    # to exist in Git and so be seen by CI.
    return content != ["__pycache__"]


def explore_module(package, explore_children):
    """Explore the modules."""
    module = importlib.import_module(package)

    found = []

    if not hasattr(module, "__path__"):
        return found

    for _, name, _ in pkgutil.iter_modules(module.__path__, f"{package}."):
        found.append(name)

        if explore_children:
            found.extend(explore_module(name, False))

    return found


def core_requirements():
    """Gather core requirements out of setup.py."""
    reqs_raw = re.search(
        r"REQUIRES = \[(.*?)\]", Path("setup.py").read_text(), re.S
    ).group(1)
    return [x[1] for x in re.findall(r"(['\"])(.*?)\1", reqs_raw)]


def gather_recursive_requirements(domain, seen=None):
    """Recursively gather requirements from a module."""
    if seen is None:
        seen = set()

    seen.add(domain)
    integration = Integration(Path(f"homeassistant/components/{domain}"))
    integration.load_manifest()
    reqs = set(integration.requirements)
    for dep_domain in integration.dependencies:
        reqs.update(gather_recursive_requirements(dep_domain, seen))
    return reqs


def comment_requirement(req):
    """Comment out requirement. Some don't install on all systems."""
    return any(ign.lower() in req.lower() for ign in COMMENT_REQUIREMENTS)


def gather_modules():
    """Collect the information."""
    reqs = {}

    errors = []

    gather_requirements_from_manifests(errors, reqs)
    gather_requirements_from_modules(errors, reqs)

    for key in reqs:
        reqs[key] = sorted(reqs[key], key=lambda name: (len(name.split(".")), name))

    if errors:
        print("******* ERROR")
        print("Errors while importing: ", ", ".join(errors))
        return None

    return reqs


def gather_requirements_from_manifests(errors, reqs):
    """Gather all of the requirements from manifests."""
    integrations = Integration.load_dir(Path("homeassistant/components"))
    for domain in sorted(integrations):
        integration = integrations[domain]

        if not integration.manifest:
            errors.append(f"The manifest for integration {domain} is invalid.")
            continue

        process_requirements(
            errors, integration.requirements, f"homeassistant.components.{domain}", reqs
        )


def gather_requirements_from_modules(errors, reqs):
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


def process_requirements(errors, module_requirements, package, reqs):
    """Process all of the requirements."""
    for req in module_requirements:
        if "://" in req:
            errors.append(f"{package}[Only pypi dependencies are allowed: {req}]")
        if req.partition("==")[1] == "" and req not in IGNORE_PIN:
            errors.append(f"{package}[Please pin requirement {req}, see {URL_PIN}]")
        reqs.setdefault(req, []).append(package)


def generate_requirements_list(reqs):
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


def requirements_output(reqs):
    """Generate output for requirements."""
    output = [
        "-c homeassistant/package_constraints.txt\n",
        "\n",
        "# Home Assistant Core\n",
    ]
    output.append("\n".join(core_requirements()))
    output.append("\n")

    return "".join(output)


def requirements_all_output(reqs):
    """Generate output for requirements_all."""
    output = [
        "# Home Assistant Core, full dependency set\n"
        "-c homeassistant/package_constraints.txt\n",
        "-r requirements.txt\n",
    ]
    output.append(generate_requirements_list(reqs))

    return "".join(output)


def requirements_test_output(reqs):
    """Generate output for test_requirements."""
    output = [
        "# Home Assistant tests, full dependency set\n",
        f"# Automatically generated by {Path(__file__).name}, do not edit\n",
        "\n",
        "-c homeassistant/package_constraints.txt\n",
    ]
    output.append("-r requirements_test.txt\n")

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


def requirements_pre_commit_output():
    """Generate output for pre-commit dependencies."""
    source = ".pre-commit-config.yaml"
    pre_commit_conf = load_yaml(source)
    reqs = []
    for repo in (x for x in pre_commit_conf["repos"] if x.get("rev")):
        for hook in repo["hooks"]:
            if hook["id"] not in IGNORE_PRE_COMMIT_HOOK_ID:
                reqs.append(f"{hook['id']}=={repo['rev'].lstrip('v')}")
                reqs.extend(x for x in hook.get("additional_dependencies", ()))
    output = [
        f"# Automatically generated "
        f"from {source} by {Path(__file__).name}, do not edit",
        "",
    ]
    output.extend(sorted(reqs))
    return "\n".join(output) + "\n"


def gather_constraints():
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


def diff_file(filename, content):
    """Diff a file."""
    return list(
        difflib.context_diff(
            [f"{line}\n" for line in Path(filename).read_text().split("\n")],
            [f"{line}\n" for line in content.split("\n")],
            filename,
            "generated",
        )
    )


def main(validate):
    """Run the script."""
    if not os.path.isfile("requirements_all.txt"):
        print("Run this from HA root dir")
        return 1

    data = gather_modules()

    if data is None:
        return 1

    reqs_file = requirements_output(data)
    reqs_all_file = requirements_all_output(data)
    reqs_test_file = requirements_test_output(data)
    reqs_pre_commit_file = requirements_pre_commit_output()
    constraints = gather_constraints()

    files = (
        ("requirements.txt", reqs_file),
        ("requirements_all.txt", reqs_all_file),
        ("requirements_test_pre_commit.txt", reqs_pre_commit_file),
        ("requirements_test_all.txt", reqs_test_file),
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
