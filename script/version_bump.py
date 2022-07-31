#!/usr/bin/env python3
"""Helper script to bump the current version."""
import argparse
from datetime import datetime
import re
import subprocess

from packaging.version import Version

from homeassistant import const


def _bump_release(release, bump_type):
    """Bump a release tuple consisting of 3 numbers."""
    major, minor, patch = release

    if bump_type == "patch":
        patch += 1
    elif bump_type == "minor":
        minor += 1
        patch = 0

    return major, minor, patch


def bump_version(version, bump_type):
    """Return a new version given a current version and action."""
    to_change = {}

    if bump_type == "minor":
        # Convert 0.67.3 to 0.68.0
        # Convert 0.67.3.b5 to 0.68.0
        # Convert 0.67.3.dev0 to 0.68.0
        # Convert 0.67.0.b5 to 0.67.0
        # Convert 0.67.0.dev0 to 0.67.0
        to_change["dev"] = None
        to_change["pre"] = None

        if not version.is_prerelease or version.release[2] != 0:
            to_change["release"] = _bump_release(version.release, "minor")

    elif bump_type == "patch":
        # Convert 0.67.3 to 0.67.4
        # Convert 0.67.3.b5 to 0.67.3
        # Convert 0.67.3.dev0 to 0.67.3
        to_change["dev"] = None
        to_change["pre"] = None

        if not version.is_prerelease:
            to_change["release"] = _bump_release(version.release, "patch")

    elif bump_type == "dev":
        # Convert 0.67.3 to 0.67.4.dev0
        # Convert 0.67.3.b5 to 0.67.4.dev0
        # Convert 0.67.3.dev0 to 0.67.3.dev1
        if version.is_devrelease:
            to_change["dev"] = ("dev", version.dev + 1)
        else:
            to_change["pre"] = ("dev", 0)
            to_change["release"] = _bump_release(version.release, "minor")

    elif bump_type == "beta":
        # Convert 0.67.5 to 0.67.6b0
        # Convert 0.67.0.dev0 to 0.67.0b0
        # Convert 0.67.5.b4 to 0.67.5b5

        if version.is_devrelease:
            to_change["dev"] = None
            to_change["pre"] = ("b", 0)

        elif version.is_prerelease:
            if version.pre[0] == "a":
                to_change["pre"] = ("b", 0)
            if version.pre[0] == "b":
                to_change["pre"] = ("b", version.pre[1] + 1)
            else:
                to_change["pre"] = ("b", 0)
                to_change["release"] = _bump_release(version.release, "patch")

        else:
            to_change["release"] = _bump_release(version.release, "patch")
            to_change["pre"] = ("b", 0)

    elif bump_type == "nightly":
        # Convert 0.70.0d0 to 0.70.0d20190424, fails when run on non dev release
        if not version.is_devrelease:
            raise ValueError("Can only be run on dev release")

        to_change["dev"] = (
            "dev",
            datetime.utcnow().date().isoformat().replace("-", ""),
        )

    else:
        assert False, f"Unsupported type: {bump_type}"

    temp = Version("0")
    temp._version = version._version._replace(**to_change)
    return Version(str(temp))


def write_version(version):
    """Update Home Assistant constant file with new version."""
    with open("homeassistant/const.py") as fil:
        content = fil.read()

    major, minor, patch = str(version).split(".", 2)

    content = re.sub(
        "MAJOR_VERSION: Final = .*\n", f"MAJOR_VERSION: Final = {major}\n", content
    )
    content = re.sub(
        "MINOR_VERSION: Final = .*\n", f"MINOR_VERSION: Final = {minor}\n", content
    )
    content = re.sub(
        "PATCH_VERSION: Final = .*\n", f'PATCH_VERSION: Final = "{patch}"\n', content
    )

    with open("homeassistant/const.py", "wt") as fil:
        fil.write(content)


def write_version_metadata(version: Version) -> None:
    """Update pyproject.toml file with new version."""
    with open("pyproject.toml", encoding="utf8") as fp:
        content = fp.read()

    content = re.sub(r"(version\W+=\W).+\n", f'\\g<1>"{version}"\n', content, count=1)

    with open("pyproject.toml", "w", encoding="utf8") as fp:
        fp.write(content)


def write_ci_workflow(version: Version) -> None:
    """Update ci workflow with new version."""
    with open(".github/workflows/ci.yaml") as fp:
        content = fp.read()

    short_version = ".".join(str(version).split(".", maxsplit=2)[:2])
    content = re.sub(
        r"(\n\W+HA_SHORT_VERSION: )\d{4}\.\d{1,2}\n",
        f"\\g<1>{short_version}\n",
        content,
        count=1,
    )

    with open(".github/workflows/ci.yaml", "w") as fp:
        fp.write(content)


def main():
    """Execute script."""
    parser = argparse.ArgumentParser(description="Bump version of Home Assistant")
    parser.add_argument(
        "type",
        help="The type of the bump the version to.",
        choices=["beta", "dev", "patch", "minor", "nightly"],
    )
    parser.add_argument(
        "--commit", action="store_true", help="Create a version bump commit."
    )
    arguments = parser.parse_args()

    if arguments.commit and subprocess.run(["git", "diff", "--quiet"]).returncode == 1:
        print("Cannot use --commit because git is dirty.")
        return

    current = Version(const.__version__)
    bumped = bump_version(current, arguments.type)
    assert bumped > current, "BUG! New version is not newer than old version"

    write_version(bumped)
    write_version_metadata(bumped)
    write_ci_workflow(bumped)
    print(bumped)

    if not arguments.commit:
        return

    subprocess.run(["git", "commit", "-nam", f"Bumped version to {bumped}"])


def test_bump_version():
    """Make sure it all works."""
    import pytest

    assert bump_version(Version("0.56.0"), "beta") == Version("0.56.1b0")
    assert bump_version(Version("0.56.0b3"), "beta") == Version("0.56.0b4")
    assert bump_version(Version("0.56.0.dev0"), "beta") == Version("0.56.0b0")

    assert bump_version(Version("0.56.3"), "dev") == Version("0.57.0.dev0")
    assert bump_version(Version("0.56.0b3"), "dev") == Version("0.57.0.dev0")
    assert bump_version(Version("0.56.0.dev0"), "dev") == Version("0.56.0.dev1")

    assert bump_version(Version("0.56.3"), "patch") == Version("0.56.4")
    assert bump_version(Version("0.56.3.b3"), "patch") == Version("0.56.3")
    assert bump_version(Version("0.56.0.dev0"), "patch") == Version("0.56.0")

    assert bump_version(Version("0.56.0"), "minor") == Version("0.57.0")
    assert bump_version(Version("0.56.3"), "minor") == Version("0.57.0")
    assert bump_version(Version("0.56.0.b3"), "minor") == Version("0.56.0")
    assert bump_version(Version("0.56.3.b3"), "minor") == Version("0.57.0")
    assert bump_version(Version("0.56.0.dev0"), "minor") == Version("0.56.0")
    assert bump_version(Version("0.56.2.dev0"), "minor") == Version("0.57.0")

    today = datetime.utcnow().date().isoformat().replace("-", "")
    assert bump_version(Version("0.56.0.dev0"), "nightly") == Version(
        f"0.56.0.dev{today}"
    )
    with pytest.raises(ValueError):
        assert bump_version(Version("0.56.0"), "nightly")


if __name__ == "__main__":
    main()
