"""Validate coverage files."""

from __future__ import annotations

from pathlib import Path

from .model import Config, Integration

DONT_IGNORE = (
    "config_flow.py",
    "device_action.py",
    "device_condition.py",
    "device_trigger.py",
    "diagnostics.py",
    "group.py",
    "intent.py",
    "logbook.py",
    "media_source.py",
    "recorder.py",
    "scene.py",
)

CORE_PREFIX = """# Sorted by hassfest.
#
# To sort, run python3 -m script.hassfest -p coverage

[run]
source = homeassistant
omit =
"""
COMPONENTS_PREFIX = (
    "    # omit pieces of code that rely on external devices being present\n"
)
SUFFIX = """[report]
# Regexes for lines to exclude from consideration
exclude_lines =
    # Have to re-enable the standard pragma
    pragma: no cover

    # Don't complain about missing debug-only code:
    def __repr__

    # Don't complain if tests don't hit defensive assertion code:
    raise AssertionError
    raise NotImplementedError

    # TYPE_CHECKING and @overload blocks are never executed during pytest run
    if TYPE_CHECKING:
    @overload
"""


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate coverage."""
    coverage_path = config.root / ".coveragerc"

    not_found: list[str] = []
    unsorted: list[str] = []
    checking = False

    previous_line = ""
    with coverage_path.open("rt") as fp:
        for line in fp:
            line = line.strip()

            if line == COMPONENTS_PREFIX.strip():
                previous_line = ""
                continue

            if not line or line.startswith("#"):
                continue

            if not checking:
                if line == "omit =":
                    checking = True
                continue

            # Finished
            if line == "[report]":
                break

            path = Path(line)

            # Discard wildcard
            path_exists = path
            while "*" in path_exists.name:
                path_exists = path_exists.parent

            if not path_exists.exists():
                not_found.append(line)
                continue

            if line < previous_line:
                unsorted.append(line)
            previous_line = line

            if not line.startswith("homeassistant/components/"):
                continue

            # Ignore sub-directories
            if len(path.parts) > 4:
                continue

            integration_path = path.parent

            integration = integrations[integration_path.name]

            if (
                path.parts[-1] == "*"
                and Path(f"tests/components/{integration.domain}/__init__.py").exists()
            ):
                integration.add_error(
                    "coverage",
                    "has tests and should not use wildcard in .coveragerc file",
                )

            for check in DONT_IGNORE:
                if path.parts[-1] not in {"*", check}:
                    continue

                if (integration_path / check).exists():
                    integration.add_error(
                        "coverage",
                        f"{check} must not be ignored by the .coveragerc file",
                    )

    if unsorted:
        config.add_error(
            "coverage",
            "Paths are unsorted in .coveragerc file. "
            "Run python3 -m script.hassfest\n  - "
            f"{'\n  - '.join(unsorted)}",
            fixable=True,
        )

    if not_found:
        raise RuntimeError(
            f".coveragerc references files that don't exist: {', '.join(not_found)}."
        )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Sort coverage."""
    coverage_path = config.root / ".coveragerc"
    core = []
    components = []
    section = "header"

    with coverage_path.open("rt") as fp:
        for line in fp:
            if line == "[report]\n":
                break

            if section != "core" and line == "omit =\n":
                section = "core"
            elif section != "components" and line == COMPONENTS_PREFIX:
                section = "components"
            elif section == "core" and line != "\n":
                core.append(line)
            elif section == "components" and line != "\n":
                components.append(line)

    assert core, "core should be a non-empty list"
    assert components, "components should be a non-empty list"
    content = (
        f"{CORE_PREFIX}{"".join(sorted(core))}\n"
        f"{COMPONENTS_PREFIX}{"".join(sorted(components))}\n"
        f"\n{SUFFIX}"
    )

    with coverage_path.open("w") as fp:
        fp.write(content)
