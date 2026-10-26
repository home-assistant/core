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
from typing import Any, Literal

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
    version: str
    branch: str
    items: list[Item] = field(default_factory=list)


@dataclass
class Constants:
    """Module-level string constants, per file and per group."""

    files: dict[str, dict[str, str]] = field(default_factory=dict)
    groups: dict[str, dict[str, set[str]]] = field(default_factory=dict)

    def add(self, file: str, constants: dict[str, str]) -> None:
        """Add the constants defined in a file."""
        self.files[file] = constants
        values = self.groups.setdefault(group_name(file)[0], {})
        for name, value in constants.items():
            values.setdefault(name, set()).add(value)

    def resolve(self, file: str, name: str) -> str | None:
        """Resolve a constant used in a file.

        A constant defined in the file itself wins. Otherwise it must have one
        value across the group; names with several values are left unresolved.
        """
        if name in self.files[file]:
            return self.files[file][name]
        values = self.groups[group_name(file)[0]].get(name, set())
        return next(iter(values)) if len(values) == 1 else None


def parse_version(value: str) -> tuple[int, int] | None:
    """Return (major, minor) for a version string, or None if not a version."""
    if match := _VERSION_MATCH.match(value):
        return int(match[1]), int(match[2])
    return None


def dev_version(root: Path) -> tuple[int, int]:
    """Read the current major and minor version from homeassistant/const.py."""
    text = (root / "homeassistant/const.py").read_text()
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


def enclosing_functions(
    tree: ast.Module,
) -> dict[ast.AST, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Map each node to the innermost function that contains it."""
    owners: dict[ast.AST, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    # ast.walk is breadth first, so inner functions overwrite outer ones.
    for func in ast.walk(tree):
        if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for node in ast.walk(func):
                owners[node] = func
    return owners


def find_parameter(
    func: ast.FunctionDef | ast.AsyncFunctionDef, name: str
) -> tuple[int | None, ast.expr | None] | None:
    """Return the positional index and default of a parameter, if it is one."""
    args = func.args
    positional = [*args.posonlyargs, *args.args]
    defaults: list[ast.expr | None] = [
        *([None] * (len(positional) - len(args.defaults))),
        *args.defaults,
    ]
    for index, arg in enumerate(positional):
        if arg.arg == name:
            return index, defaults[index]
    for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        if arg.arg == name:
            return None, default
    return None


def passed_argument(
    call: ast.Call, name: str, index: int | None
) -> ast.expr | Literal[False] | None:
    """Return what a call passes for a parameter.

    Returns the argument, False when the call leaves it to the default, or None
    when it can't tell because of *args or **kwargs.
    """
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    if any(keyword.arg is None for keyword in call.keywords):
        return None
    if index is not None:
        if any(isinstance(arg, ast.Starred) for arg in call.args[: index + 1]):
            return None
        if len(call.args) > index:
            return call.args[index]
    return False


def resolve_version(value: ast.expr, constants: Constants, file: str) -> str | None:
    """Return the version string of a literal or an upper-case constant."""
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    if isinstance(value, ast.Name) and value.id.isupper():
        return constants.resolve(file, value.id)
    return None


def caller_items(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    func_file: str,
    parameter: str,
    files: list[tuple[str, str, ast.Module]],
    constants: Constants,
) -> list[Item] | None:
    """Resolve a forwarded parameter to the versions its callers end up using.

    Only callers in the same integration or core module are searched. Returns
    None when there are none, or when one of them can't be resolved.
    """
    if (found := find_parameter(func, parameter)) is None:
        return None
    index, default = found
    is_method = bool(func.args.args) and func.args.args[0].arg in ("self", "cls")
    items = []
    for rel, text, tree in files:
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call):
                continue
            if isinstance(call.func, ast.Name) and call.func.id == func.name:
                call_index = index
            elif isinstance(call.func, ast.Attribute) and call.func.attr == func.name:
                call_index = index - 1 if index is not None and is_method else index
            else:
                continue
            argument = passed_argument(call, parameter, call_index)
            if argument is None:
                return None
            if argument is False:
                if default is None:
                    return None
                version = resolve_version(default, constants, func_file)
                source = f"{func.name}() default {parameter}={ast.unparse(default)}"
            else:
                version = resolve_version(argument, constants, rel)
                source = ast.get_source_segment(text, argument) or ""
            if version is None:
                return None
            items.append(Item(rel, call.lineno, version, source))
    return items or None


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


def _group_order(key: tuple[str, str]) -> tuple[str, int, int]:
    """Sort groups by name, then by version."""
    major, minor = key[1].split(".")
    return key[0], int(major), int(minor)


def scan(root: Path, current: tuple[int, int]) -> dict[str, Any]:
    """Find the deprecations under root/homeassistant that are due at current."""
    trees: dict[str, tuple[str, ast.Module]] = {}
    group_files: dict[str, list[tuple[str, str, ast.Module]]] = {}
    constants = Constants()
    for path in sorted((root / "homeassistant").rglob("*.py")):
        text = path.read_text()
        tree = ast.parse(text)
        rel = path.relative_to(root).as_posix()
        name = group_name(rel)[0]
        constants.add(rel, module_constants(tree))
        group_files.setdefault(name, []).append((rel, text, tree))
        if KEY in text or any(cls in text for cls in POSITIONAL):
            trees[rel] = (text, tree)

    groups: dict[tuple[str, str], Group] = {}
    unresolved: list[Item] = []
    passthrough: list[Item] = []
    for rel, (text, tree) in trees.items():
        name, kind = group_name(rel)
        owners = enclosing_functions(tree)
        for value in find_values(tree):
            if isinstance(value, ast.Constant) and value.value is None:
                continue
            item = Item(
                rel, value.lineno, None, ast.get_source_segment(text, value) or ""
            )
            if isinstance(value, ast.Constant) or (
                isinstance(value, ast.Name) and value.id.isupper()
            ):
                item.version = resolve_version(value, constants, rel)
                items = [item]
            elif (
                isinstance(value, ast.Name)
                and (func := owners.get(value)) is not None
                and (
                    callers := caller_items(
                        func, rel, value.id, group_files[name], constants
                    )
                )
                is not None
            ):
                items = callers
            else:
                # A variable or attribute forwarded from outside this group.
                passthrough.append(item)
                continue
            for found in items:
                parsed = parse_version(found.version) if found.version else None
                if parsed is None:
                    unresolved.append(found)
                    continue
                if parsed > current:
                    continue
                version = f"{parsed[0]}.{parsed[1]}"
                groups.setdefault(
                    (name, version),
                    Group(name, kind, version, branch_name(name, version)),
                ).items.append(found)

    return {
        "current_version": f"{current[0]}.{current[1]}",
        "groups": [asdict(groups[key]) for key in sorted(groups, key=_group_order)],
        "unresolved": [asdict(item) for item in unresolved],
        "passthrough": [asdict(item) for item in passthrough],
    }


def main() -> None:
    """Run the scan from the repository root and print the result as JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        help="Treat this X.Y as the current version instead of the one in const.py",
    )
    args = parser.parse_args()
    root = Path.cwd()
    if not (root / "homeassistant/const.py").is_file():
        sys.exit("Run this from the root of a home-assistant/core checkout")
    if args.version:
        if (current := parse_version(args.version)) is None:
            sys.exit(f"Invalid version: {args.version}")
    else:
        current = dev_version(root)
    print(json.dumps(scan(root, current), indent=2))


if __name__ == "__main__":
    main()
