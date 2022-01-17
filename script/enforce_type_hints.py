#!/usr/bin/env python3
"""Cleanup components."""
from __future__ import annotations

from dataclasses import dataclass
import re
import sys

import black
import isort
import yaml

from homeassistant.const import Platform

_BLACK_MODE = black.Mode(target_versions={black.TargetVersion.PY38})
_ISORT_CONFIG = isort.Config("pyproject.toml")
_IGNORE_CORE = False
_IGNORED_FILES: list[str] = []

with open(".core_files.yaml", encoding="utf8") as file:
    _CORE_FILES = yaml.safe_load(file)


@dataclass
class PatternMatch:
    """Class for pattern matching."""

    pattern: str
    repl: str
    imports: list[str]
    groups: dict[int, list[str] | str]
    disabled: bool = False


components = ("[a-z]",)

_REGEX_SPACE = r"[\s]*"
_REGEX_LAST_ARGUMENT_SPACE = f"{_REGEX_SPACE},?{_REGEX_SPACE}"

_REGEX_METHOD_NAME = r"([a-z_]+)"

_REGEX_ARGUMENT_NAME = r"([a-zA-Z_\s]+)"
_REGEX_ARGUMENT_TYPEHINT = r"(?:[:\s]+)?([|a-zA-Z\s\.]*)?"
_REGEX_ARGUMENT_DEFAULT = r"(?:\s?=\s?[a-zA-Z]+)?"
_REGEX_ARGUMENT = (
    f"{_REGEX_ARGUMENT_NAME}{_REGEX_ARGUMENT_TYPEHINT}{_REGEX_ARGUMENT_DEFAULT}"
)

_REGEX_RETURN_TYPEHINT = r"(?:[->\s]+)?([|a-zA-Z\.\[\]\s]*)?"

_SUBSTITUTIONS: dict[str | Platform, list[PatternMatch]] = {}


def _is_file_in_ignore_list(name: str) -> bool:
    for ignore_file in _IGNORED_FILES:
        ignore_file = ignore_file.strip("*")
        if name.startswith(ignore_file):
            return True
    if not _IGNORE_CORE:
        return False
    for key in ("base_platforms", "components"):
        for ignore_file in _CORE_FILES[key]:
            ignore_file = ignore_file.strip("*")
            if name.startswith(ignore_file):
                return True
    return False


def _convert_import_string(import_string: str, match: re.Match[str]) -> str:
    """Convert groups inside import_string."""
    if "\\g<" not in import_string:
        return import_string
    for key in range(len(match.groups())):
        import_string = import_string.replace(f"\\g<{key}>", match.group(key))
    return import_string


def _process_file(name: str, subs: list[PatternMatch]) -> None:
    """Process file."""
    if _is_file_in_ignore_list(name):
        return
    modified = False
    with open(name, encoding="utf-8") as file1:
        content = file1.read()
    for pattern_match in subs:
        if pattern_match.disabled:
            continue
        needs_update = False

        match = re.search(pattern_match.pattern, content, re.MULTILINE)
        if not match:
            continue

        if not pattern_match.groups:
            needs_update = True

        for group_id, target_hint in pattern_match.groups.items():
            if needs_update:
                break
            target_hint = (
                target_hint if isinstance(target_hint, list) else [target_hint]
            )
            current_hint = match.group(group_id)
            if current_hint is not None:
                current_hint = current_hint.strip()
            if current_hint not in target_hint:
                print(f"`{current_hint}` not in `{target_hint}`")
                needs_update = True

        if needs_update:
            new_content = re.sub(
                pattern_match.pattern, pattern_match.repl, content, re.MULTILINE
            )
            for import_string in pattern_match.imports:
                import_string = _convert_import_string(import_string, match)
                if import_string in new_content:
                    continue
                index = new_content.find('"""\n', 4)
                new_content = (
                    new_content[: index + 4]
                    + import_string
                    + "\n"
                    + new_content[index + 4 :]
                )

            if content != new_content:
                new_content = isort.code(new_content, config=_ISORT_CONFIG)

            if content != new_content:
                new_content = black.format_str(new_content, mode=_BLACK_MODE)

            if content != new_content:
                print(f"{name}: found '{match}'...")
                content = new_content
                modified = True

    if modified:

        with open(name, "w", encoding="utf-8") as file1:
            file1.write(content)


_SUBSTITUTIONS["__init__"] = [
    PatternMatch(
        pattern=f"\\ndef setup\\({_REGEX_SPACE}{_REGEX_ARGUMENT},{_REGEX_SPACE}{_REGEX_ARGUMENT}{_REGEX_LAST_ARGUMENT_SPACE}\\){_REGEX_RETURN_TYPEHINT}:",
        repl=r"\ndef setup(\g<1>: HomeAssistant, \g<3>: ConfigType) -> bool:",
        imports=[
            "from homeassistant.core import HomeAssistant",
            "from homeassistant.helpers.typing import ConfigType",
        ],
        groups={2: "HomeAssistant", 4: "ConfigType", 5: "bool"},
    ),
    PatternMatch(
        pattern=f"\\nasync def async_setup\\({_REGEX_SPACE}{_REGEX_ARGUMENT},{_REGEX_SPACE}{_REGEX_ARGUMENT}{_REGEX_LAST_ARGUMENT_SPACE}\\){_REGEX_RETURN_TYPEHINT}:",
        repl=r"\nasync def async_setup(\g<1>: HomeAssistant, \g<3>: ConfigType) -> bool:",
        imports=[
            "from homeassistant.core import HomeAssistant",
            "from homeassistant.helpers.typing import ConfigType",
        ],
        groups={2: ["ha.HomeAssistant", "HomeAssistant"], 4: "ConfigType", 5: "bool"},
    ),
    PatternMatch(
        pattern=f"\\nasync def async_setup_entry\\({_REGEX_SPACE}{_REGEX_ARGUMENT},{_REGEX_SPACE}{_REGEX_ARGUMENT}{_REGEX_LAST_ARGUMENT_SPACE}\\){_REGEX_RETURN_TYPEHINT}:",
        repl=r"\nasync def async_setup_entry(\g<1>: HomeAssistant, \g<3>: ConfigEntry) -> bool:",
        imports=[
            "from homeassistant.core import HomeAssistant",
            "from homeassistant.config_entries import ConfigEntry",
        ],
        groups={2: "HomeAssistant", 4: "ConfigEntry", 5: "bool"},
    ),
    PatternMatch(
        pattern=f"\\nasync def async_remove_entry\\({_REGEX_SPACE}{_REGEX_ARGUMENT},{_REGEX_SPACE}{_REGEX_ARGUMENT}{_REGEX_LAST_ARGUMENT_SPACE}\\){_REGEX_RETURN_TYPEHINT}:",
        repl=r"\nasync def async_remove_entry(\g<1>: HomeAssistant, \g<3>: ConfigEntry) -> None:",
        imports=[
            "from homeassistant.core import HomeAssistant",
            "from homeassistant.config_entries import ConfigEntry",
        ],
        groups={2: "HomeAssistant", 4: "ConfigEntry", 5: "None"},
    ),
    PatternMatch(
        pattern=f"\\nasync def async_unload_entry\\({_REGEX_SPACE}{_REGEX_ARGUMENT},{_REGEX_SPACE}{_REGEX_ARGUMENT}{_REGEX_LAST_ARGUMENT_SPACE}\\){_REGEX_RETURN_TYPEHINT}:",
        repl=r"\nasync def async_unload_entry(\g<1>: HomeAssistant, \g<3>: ConfigEntry) -> bool:",
        imports=[
            "from homeassistant.core import HomeAssistant",
            "from homeassistant.config_entries import ConfigEntry",
        ],
        groups={2: "HomeAssistant", 4: "ConfigEntry", 5: "bool"},
    ),
    PatternMatch(
        pattern=f"\\nasync def async_migrate_entry\\({_REGEX_SPACE}{_REGEX_ARGUMENT},{_REGEX_SPACE}{_REGEX_ARGUMENT}{_REGEX_LAST_ARGUMENT_SPACE}\\){_REGEX_RETURN_TYPEHINT}:",
        repl=r"\nasync def async_migrate_entry(\g<1>: HomeAssistant, \g<3>: ConfigEntry) -> bool:",
        imports=[
            "from homeassistant.core import HomeAssistant",
            "from homeassistant.config_entries import ConfigEntry",
        ],
        groups={2: "HomeAssistant", 4: "ConfigEntry", 5: "bool"},
    ),
]

_SUBSTITUTIONS["platform"] = [
    PatternMatch(
        pattern=f"\\ndef setup_platform\\({_REGEX_SPACE}{_REGEX_ARGUMENT},{_REGEX_SPACE}{_REGEX_ARGUMENT},{_REGEX_SPACE}{_REGEX_ARGUMENT},{_REGEX_SPACE}{_REGEX_ARGUMENT}{_REGEX_LAST_ARGUMENT_SPACE}\\){_REGEX_RETURN_TYPEHINT}:",
        repl=r"\ndef setup_platform(\g<1>: HomeAssistant, \g<3>: ConfigType, \g<5>: AddEntitiesCallback, \g<7>: DiscoveryInfoType | None = None) -> None:",
        imports=[
            "from homeassistant.core import HomeAssistant",
            "from homeassistant.helpers.typing import ConfigType",
            "from homeassistant.helpers.typing import DiscoveryInfoType",
            "from homeassistant.helpers.entity_platform import AddEntitiesCallback",
            "from __future__ import annotations",
        ],
        groups={
            2: "HomeAssistant",
            4: "ConfigType",
            6: "AddEntitiesCallback",
            8: "DiscoveryInfoType | None",
            9: "None",
        },
    ),
    PatternMatch(
        pattern=f"\\nasync def async_setup_platform\\({_REGEX_SPACE}{_REGEX_ARGUMENT},{_REGEX_SPACE}{_REGEX_ARGUMENT},{_REGEX_SPACE}{_REGEX_ARGUMENT},{_REGEX_SPACE}{_REGEX_ARGUMENT}{_REGEX_LAST_ARGUMENT_SPACE}\\){_REGEX_RETURN_TYPEHINT}:",
        repl=r"\nasync def async_setup_platform(\g<1>: HomeAssistant, \g<3>: ConfigType, \g<5>: AddEntitiesCallback, \g<7>: DiscoveryInfoType | None = None) -> None:",
        imports=[
            "from homeassistant.core import HomeAssistant",
            "from homeassistant.helpers.typing import ConfigType",
            "from homeassistant.helpers.typing import DiscoveryInfoType",
            "from homeassistant.helpers.entity_platform import AddEntitiesCallback",
            "from __future__ import annotations",
        ],
        groups={
            2: "HomeAssistant",
            4: "ConfigType",
            6: "AddEntitiesCallback",
            8: "DiscoveryInfoType | None",
            9: "None",
        },
    ),
    PatternMatch(
        pattern=f"\\nasync def async_setup_entry\\({_REGEX_SPACE}{_REGEX_ARGUMENT},{_REGEX_SPACE}{_REGEX_ARGUMENT},{_REGEX_SPACE}{_REGEX_ARGUMENT}{_REGEX_LAST_ARGUMENT_SPACE}\\){_REGEX_RETURN_TYPEHINT}:",
        repl=r"\nasync def async_setup_entry(\g<1>: HomeAssistant, \g<3>: ConfigEntry, \g<5>: AddEntitiesCallback) -> None:",
        imports=[
            "from homeassistant.core import HomeAssistant",
            "from homeassistant.config_entries import ConfigEntry",
            "from homeassistant.helpers.entity_platform import AddEntitiesCallback",
        ],
        groups={
            2: "HomeAssistant",
            4: "ConfigEntry",
            6: "AddEntitiesCallback",
            7: "None",
        },
    ),
]


def main(filenames: list[str]) -> None:
    """Process files."""
    for filename in filenames:
        if re.match("homeassistant/components/[^/]+/__init__.py", filename):
            _process_file(filename, _SUBSTITUTIONS["__init__"])

        for platform in Platform:
            if re.match(
                f"homeassistant/components/[^/]+/{platform.value}.py", filename
            ):
                _process_file(filename, _SUBSTITUTIONS["platform"])


if __name__ == "__main__":
    files = sys.argv[1:]
    main(files)
