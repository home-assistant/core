"""Pypi name validator."""

import asyncio
from dataclasses import dataclass
import os
import re
import sys

from aiohttp import ClientResponseError, ClientSession
from unidiff import PatchSet
from unidiff.patch import Hunk, Line

from script.util import async_safe_exec

_FILES_TO_CHECK = ["requirements*.txt", "homeassistant/package_constraints.txt"]
_CORE_NAME_MATCHER = re.compile(
    r"^(?P<name>\S+)\s+https://github\.com/home-assistant/core"
)

# https://peps.python.org/pep-0508/#names
_PYPI_NAME_REGEX = r"^(?P<name>([A-Z\d]([\w.-]*[A-Z\d])+))"
_PYPI_ENDPOINT = "https://pypi.org/pypi"


@dataclass(frozen=True)
class NameConflcit:
    """Name conflict data class."""

    actual: str
    expected: str


class ResultHandler:
    """Result instance."""

    name_conflicts: list[NameConflcit] = []
    errors: list[str] = []

    def print_result(self) -> bool:
        """Print result and return True if validation succeeded with any error."""
        success = True
        if self.name_conflicts:
            success = False
            print(
                "The following requirements should be renamed to match their name correctly:"
            )
            for conflict in self.name_conflicts:
                print("*", f'"{conflict.actual}" to "{conflict.expected}"')

        if self.errors:
            success = False
            print("The following occurred:")
            for error in self.errors:
                print("*", error)

        if success:
            print("Validation successful.")

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


async def get_diff() -> PatchSet:
    """Return diff."""
    base_branch = "dev"
    if remote := (await find_core_remote_name()):
        base_branch = f"{remote}/{base_branch}"

    base_commit = await find_merge_base(base_branch)

    log = await async_safe_exec("git", "diff", f"{base_commit}...", *_FILES_TO_CHECK)
    return PatchSet(log)


async def get_changed_requirements_from_diff() -> set[str]:
    """Get changed requirements from diff."""
    requirements: set[str] = set()

    diff = await get_diff()
    for file in diff:
        hunk: Hunk
        for hunk in file:
            if hunk.added:
                line: Line
                for line in hunk:
                    if line.is_added and (
                        m := re.match(
                            _PYPI_NAME_REGEX,
                            line.value,
                            re.IGNORECASE,
                        )
                    ):
                        requirements.add(m.group("name"))

    return requirements


async def validate_requirement(
    handler: ResultHandler, session: ClientSession, name: str
):
    """Validate single requirement by getting info from pypi."""
    url = "/".join([_PYPI_ENDPOINT, name, "json"])
    try:
        async with session.get(url) as res:
            res.raise_for_status()
            data = await res.json()
            if (expected := data.get("info", {}).get("name")) != name:
                handler.name_conflicts.append(NameConflcit(name, expected))
    except ClientResponseError as ex:
        handler.errors.append(ex)


async def validate_requirements(handler: ResultHandler, requirements: set[str]):
    """Validate all requirements."""
    async with ClientSession() as session, asyncio.TaskGroup() as tg:
        for requirement in requirements:
            tg.create_task(validate_requirement(handler, session, requirement))


async def main() -> int:
    """Execute script."""
    # Ensure we are in the homeassistant root
    os.chdir(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    handler = ResultHandler()

    requirements = await get_changed_requirements_from_diff()
    await validate_requirements(handler, requirements)

    if handler.print_result():
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
