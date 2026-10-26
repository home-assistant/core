#!/usr/bin/env python3
# ruff: noqa: T201
"""List breaks_in_ha_version deprecations that are due, grouped per cleanup branch."""

import argparse
import ast
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
import sys

ROOT = Path.cwd()
KEY = "breaks_in_ha_version"
# Classes in helpers/deprecation.py that take breaks_in_ha_version positionally.
POSITIONAL = {
    "DeprecatedConstant": 2,
    "DeprecatedConstantEnum": 1,
    "DeprecatedAlias": 2,
    "DeferredDeprecatedAlias": 2,
}
_VERSION_MATCH = re.compile(r"^(\d{4})\.(\d{1,2})(?:\.\d+)?$")


@dataclass
class Item:
    """A single breaks_in_ha_version occurrence."""

    file: str
    line: int
    version: str | None
    source: str


@dataclass
class Group:
    """Due items that are cleaned up together on one branch."""

    name: str
    kind: str
    oldest_version: str = ""
    branch: str = ""
    items: list[Item] = field(default_factory=list)


def parse_version(value: str) -> tuple[int, int] | None:
    """Return (major, minor) for a version string, or None if not a version."""
    if match := _VERSION_MATCH.match(value):
        return int(match[1]), int(match[2])
    return None


def dev_version() -> tuple[int, int]:
    """Read the current major and minor version from homeassistant/const.py."""
    text = (ROOT / "homeassistant/const.py").read_text()
    major = re.search(r"^MAJOR_VERSION: Final = (\d+)", text, re.MULTILINE)
    minor = re.search(r"^MINOR_VERSION: Final = (\d+)", text, re.MULTILINE)
    if not major or not minor:
        sys.exit("Could not read MAJOR_VERSION/MINOR_VERSION from const.py")
    return int(major[1]), int(minor[1])


def module_constants(tree: ast.Module) -> dict[str, str]:
    """Return the module-level string constants of a parsed file."""
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value = node.target, node.value
        else:
            continue
        if (
            isinstance(target, ast.Name)
            and isinstance(value, ast.Constant)
            and isinstance(value.value, str)
        ):
            constants[target.id] = value.value
    return constants


def find_values(tree: ast.Module) -> list[ast.expr]:
    """Find breaks_in_ha_version keyword argument and dict key values."""
    values: list[ast.expr] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == KEY:
            values.append(node.value)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and (index := POSITIONAL.get(node.func.id)) is not None
            and len(node.args) > index
        ):
            values.append(node.args[index])
        elif isinstance(node, ast.Dict):
            values.extend(
                value
                for key, value in zip(node.keys, node.values, strict=True)
                if isinstance(key, ast.Constant) and key.value == KEY
            )
    return values


def group_name(file: str) -> tuple[str, str]:
    """Return the group name and kind for a file under homeassistant/."""
    parts = file.split("/")
    if parts[1] == "components":
        return parts[2], "integration"
    return "/".join(parts[1:]), "core"


def branch_name(name: str, version: str) -> str:
    """Return the cleanup branch name for a group."""
    slug = re.sub(r"[^a-z0-9_]+", "-", name.removesuffix(".py").lower()).strip("-")
    return f"deprecation-cleanup/{slug}-{version}"


def main() -> None:
    """Run the scan and print the result as JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        help="Treat this X.Y as the current version instead of the one in const.py",
    )
    args = parser.parse_args()
    if not (ROOT / "homeassistant/const.py").is_file():
        sys.exit("Run this from the root of a home-assistant/core checkout")
    if args.version:
        if (current := parse_version(args.version)) is None:
            sys.exit(f"Invalid version: {args.version}")
    else:
        current = dev_version()

    trees: dict[str, tuple[str, ast.Module]] = {}
    constants: dict[str, dict[str, str]] = {}
    for path in sorted((ROOT / "homeassistant").rglob("*.py")):
        text = path.read_text()
        tree = ast.parse(text)
        rel = path.relative_to(ROOT).as_posix()
        name = group_name(rel)[0]
        constants.setdefault(name, {}).update(module_constants(tree))
        if KEY in text or any(cls in text for cls in POSITIONAL):
            trees[rel] = (text, tree)

    groups: dict[str, Group] = {}
    oldest: dict[str, tuple[int, int]] = {}
    unresolved: list[Item] = []
    passthrough: list[Item] = []
    for rel, (text, tree) in trees.items():
        name, kind = group_name(rel)
        for value in find_values(tree):
            if isinstance(value, ast.Constant) and value.value is None:
                continue
            item = Item(
                rel, value.lineno, None, ast.get_source_segment(text, value) or ""
            )
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                item.version = value.value
            elif isinstance(value, ast.Name) and value.id.isupper():
                item.version = constants[name].get(value.id)
            else:
                # A variable or attribute forwarded from the caller.
                passthrough.append(item)
                continue
            parsed = parse_version(item.version) if item.version else None
            if parsed is None:
                unresolved.append(item)
                continue
            if parsed > current:
                continue
            groups.setdefault(name, Group(name, kind)).items.append(item)
            oldest[name] = min(oldest.get(name, parsed), parsed)

    for name, group in groups.items():
        group.oldest_version = f"{oldest[name][0]}.{oldest[name][1]}"
        group.branch = branch_name(group.name, group.oldest_version)

    print(
        json.dumps(
            {
                "current_version": f"{current[0]}.{current[1]}",
                "groups": [asdict(group) for group in groups.values()],
                "unresolved": [asdict(item) for item in unresolved],
                "passthrough": [asdict(item) for item in passthrough],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
