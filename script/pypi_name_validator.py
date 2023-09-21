"""Pypi name validator."""

import argparse
import asyncio
from dataclasses import dataclass
from functools import partial
from glob import glob
import os
import re
import sys

from aiohttp import ClientResponseError, ClientSession
from unidiff import PatchSet
from unidiff.patch import Hunk, Line

from script.util import FAIL, PASS, async_safe_exec as _async_safe_exec, printc

async_safe_exec = partial(_async_safe_exec, print_command=False)

_FILES_TO_CHECK = ["requirements*.txt", "homeassistant/package_constraints.txt"]
_CORE_NAME_MATCHER = re.compile(
    r"^(?P<name>\S+)\s+https://github\.com/home-assistant/core"
)

# https://peps.python.org/pep-0508/#names
_PYPI_NAME_REGEX = re.compile(r"^(?P<name>([A-Z\d]([\w.-]*[A-Z\d])+))", re.IGNORECASE)
_PYPI_ENDPOINT = "https://pypi.org"


# Copied from https://github.com/pypa/pip/blob/main/src/pip/_vendor/packaging/utils.py#L27-L35
_canonicalize_regex = re.compile(r"[-_.]+")


def canonicalize_name(name: str) -> str:
    """Canonical package name."""
    # This is taken from PEP 503.
    return _canonicalize_regex.sub("-", name).lower()


@dataclass(frozen=True)
class NameConflict:
    """Name conflict data class."""

    actual: str
    expected: str


class ResultHandler:
    """Result instance."""

    name_conflicts: list[NameConflict] = []
    errors: list[str] = []

    def print_result(self) -> bool:
        """Print result and return True if validation succeeded with any error."""
        success = True
        if self.name_conflicts:
            success = False
            printc(
                FAIL,
                "The following requirements should be renamed to match Pypi's name:",
            )
            for conflict in sorted(self.name_conflicts, key=lambda n: n.actual):
                printc(FAIL, "*", f'"{conflict.actual}" to "{conflict.expected}"')

        if self.errors:
            success = False
            printc(FAIL, "The following occurred:")
            for error in self.errors:
                printc(FAIL, "*", str(error))

        if success:
            printc(PASS, "Validation successful.")

        return success


async def find_core_remote_name() -> str | None:
    """Find core remote name."""
    log = await async_safe_exec("git", "remote", "-v")
    for line in log.splitlines():
        if m := _CORE_NAME_MATCHER.match(line):
            return m.group("name")

    return None


async def find_merge_base(branch: str) -> str:
    """Find merge base."""
    log = await async_safe_exec("git", "merge-base", branch, "HEAD")
    return log.splitlines()[0]


async def get_diff(only_staged: bool) -> PatchSet:
    """Return diff."""
    if only_staged:
        return PatchSet(
            await async_safe_exec("git", "diff", "--staged", *_FILES_TO_CHECK)
        )

    base_branch = "dev"
    if remote := (await find_core_remote_name()):
        base_branch = f"{remote}/{base_branch}"

    base_commit = await find_merge_base(base_branch)

    log = await async_safe_exec("git", "diff", f"{base_commit}...", *_FILES_TO_CHECK)
    return PatchSet(log)


async def get_changed_requirements_from_diff(only_staged: bool) -> set[str]:
    """Get changed requirements from diff."""
    requirements: set[str] = set()

    diff = await get_diff(only_staged)
    for file in diff:
        hunk: Hunk
        for hunk in file:
            if hunk.added:
                line: Line
                for line in hunk:
                    if line.is_added and (m := _PYPI_NAME_REGEX.match(line.value)):
                        requirements.add(m.group("name"))

    return requirements


async def validate_requirement(
    handler: ResultHandler, session: ClientSession, name: str
):
    """Validate single requirement by getting info from pypi."""
    url = "/".join([_PYPI_ENDPOINT, "pypi", name, "json"])
    try:
        async with session.get(url) as res:
            res.raise_for_status()
            data = await res.json()
            if (expected := data.get("info", {}).get("name")) != name:
                handler.name_conflicts.append(NameConflict(name, expected))
    except ClientResponseError as ex:
        handler.errors.append(ex)


async def validate_requirements(handler: ResultHandler, requirements: set[str]):
    """Validate all requirements."""
    async with ClientSession() as session, asyncio.TaskGroup() as tg:
        for requirement in requirements:
            tg.create_task(validate_requirement(handler, session, requirement))


async def get_all_pypi_packages(handler: ResultHandler) -> set[str]:
    """Get all package names from Pypi."""
    pypi_packages: set[str] = set()
    url = _PYPI_ENDPOINT + "/simple/"
    headers = {"Accept": "application/vnd.pypi.simple.v1+json"}
    try:
        async with ClientSession() as client, client.get(url, headers=headers) as res:
            res.raise_for_status()
            data = await res.json()
            for project in data["projects"]:
                pypi_packages.add(project["name"])
    except ClientResponseError as ex:
        handler.errors.append(ex)

    return pypi_packages


def get_all_requirements_from_file() -> set[str]:
    """Get all requirements from all files found with _FILES_TO_CHECK."""
    requirements: set[str] = set()

    for pattern in _FILES_TO_CHECK:
        for file in glob(pattern):
            with open(file) as f:
                for line in f:
                    if m := _PYPI_NAME_REGEX.match(line):
                        requirements.add(m.group("name"))

    return requirements


def try_to_find_with_canonical_name(
    handler: ResultHandler, requirements: set[str], pypi_packages: set[str]
) -> set[str]:
    """Try to match with the canonical name. All packages not found in pypi_packages, will be returned."""
    req_canon = {canonicalize_name(val): val for val in requirements}
    pypi_canon = {canonicalize_name(val): val for val in pypi_packages}

    not_found_reqs: set[str] = set()
    for canonical_name, name in req_canon.items():
        if package := pypi_canon.get(canonical_name):
            handler.name_conflicts.append(NameConflict(name, package))
        else:
            # Should only happen if pypi update canonicalize_name function and we not
            not_found_reqs.add(name)

    return not_found_reqs


async def main() -> int:
    """Execute script."""
    # Ensure we are in the homeassistant root
    os.chdir(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

    parser = argparse.ArgumentParser(description="Pypi name validator")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["diff-branch", "diff-staged", "all"],
        default="diff-branch",
    )

    parsed = parser.parse_args()
    mode = parsed.mode

    handler = ResultHandler()

    requirements: set[str] = set()
    if mode != "all":
        only_staged = mode == "diff-staged"
        requirements = await get_changed_requirements_from_diff(only_staged)

    if mode == "all" or len(requirements) > 20:
        pypi_packages = await get_all_pypi_packages(handler)
        all_req = await asyncio.get_event_loop().run_in_executor(
            None, get_all_requirements_from_file
        )

        wrong_name_reqs = all_req - pypi_packages
        requirements = try_to_find_with_canonical_name(
            handler, wrong_name_reqs, pypi_packages
        )

    await validate_requirements(handler, requirements)

    if handler.print_result():
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
