#!/usr/bin/env python3
# ruff: noqa: T201
"""List breaks_in_ha_version deprecations that are due, one per cleanup branch."""

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
    "DeprecatedEntityAttr": 1,
    "DeprecatedEntityProperty": 1,
}
# Enums with deprecated members, declared as deprecated={"NAME": (replacement, version)}.
ENUM_METACLASS = "EnumWithDeprecatedMembers"
# Repair issue registry calls and the positional index of their issue_id.
ISSUE_CALLS = {"async_create_issue": 2, "create_issue": 2, "async_get_or_create": 1}
_VERSION_MATCH = re.compile(r"^(\d{4})\.(\d{1,2})(?:\.\d+)?$")


@dataclass
class Item:
    """A single breaks_in_ha_version occurrence."""

    file: str
    line: int
    version: str | None
    source: str
    issue_id: str | None = None


@dataclass
class Deprecation:
    """Due items of one deprecation, cleaned up together on one branch."""

    name: str
    kind: str
    version: str
    issue_id: str | None
    branch: str
    items: list[Item] = field(default_factory=list)


@dataclass
class Constants:
    """Module-level string constants, per file and per integration or module."""

    files: dict[str, dict[str, str]] = field(default_factory=dict)
    areas: dict[str, dict[str, set[str]]] = field(default_factory=dict)

    def add(self, file: str, constants: dict[str, str]) -> None:
        """Add the constants defined in a file."""
        self.files[file] = constants
        values = self.areas.setdefault(area_of(file)[0], {})
        for name, value in constants.items():
            values.setdefault(name, set()).add(value)

    def resolve(self, file: str, name: str) -> str | None:
        """Resolve a constant used in a file.

        A constant defined in the file itself wins. Otherwise it must have one
        value across the integration or module; names with several values are
        left unresolved.
        """
        if name in self.files[file]:
            return self.files[file][name]
        values = self.areas[area_of(file)[0]].get(name, set())
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


def call_name(call: ast.Call) -> str | None:
    """Return the name of the called function or method."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def find_values(tree: ast.Module) -> list[tuple[ast.expr, ast.Call | None]]:
    """Find breaks_in_ha_version values, with the call that takes each one."""
    values: list[tuple[ast.expr, ast.Call | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            values.extend(
                (keyword.value, node) for keyword in node.keywords if keyword.arg == KEY
            )
            # Generic classes are called as DeprecatedEntityProperty[str](...).
            func = (
                node.func.value if isinstance(node.func, ast.Subscript) else node.func
            )
            if (
                isinstance(func, ast.Name)
                and (index := POSITIONAL.get(func.id)) is not None
                and len(node.args) > index
            ):
                values.append((node.args[index], node))
        elif isinstance(node, ast.ClassDef) and any(
            keyword.arg == "metaclass"
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id == ENUM_METACLASS
            for keyword in node.keywords
        ):
            values.extend(
                (value.elts[1], None)
                for keyword in node.keywords
                if keyword.arg == "deprecated" and isinstance(keyword.value, ast.Dict)
                for value in keyword.value.values
                if isinstance(value, ast.Tuple) and len(value.elts) == 2
            )
        elif isinstance(node, ast.Dict):
            values.extend(
                (value, None)
                for key, value in zip(node.keys, node.values, strict=True)
                if isinstance(key, ast.Constant) and key.value == KEY
            )
    return values


def static_text(node: ast.expr, constants: Constants, file: str) -> str:
    """Return the fixed text of a string expression, leaving out the parts that vary."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id.isupper():
        return constants.resolve(file, node.id) or ""
    if isinstance(node, ast.FormattedValue):
        return static_text(node.value, constants, file)
    if isinstance(node, ast.JoinedStr):
        return "".join(static_text(value, constants, file) for value in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return static_text(node.left, constants, file) + static_text(
            node.right, constants, file
        )
    return ""


def issue_argument(call: ast.Call | None) -> ast.expr | None:
    """Return the issue_id argument of a repair issue registry call."""
    if call is None or (index := ISSUE_CALLS.get(call_name(call) or "")) is None:
        return None
    argument = passed_argument(call, "issue_id", index)
    return argument if isinstance(argument, ast.expr) else None


def issue_id(argument: ast.expr | None, constants: Constants, file: str) -> str | None:
    """Return a repair issue id without its varying parts."""
    if argument is None:
        return None
    return static_text(argument, constants, file).strip("_-/. ") or None


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
    if index is not None:
        if any(isinstance(arg, ast.Starred) for arg in call.args[: index + 1]):
            return None
        if len(call.args) > index:
            return call.args[index]
    if any(keyword.arg is None for keyword in call.keywords):
        return None
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
    version_arg: ast.expr,
    issue_arg: ast.expr | None,
    files: list[tuple[str, str, ast.Module]],
    constants: Constants,
) -> list[Item] | None:
    """Resolve a helper's version and issue id at each of its callers.

    Either can be forwarded from the callers through a parameter. Only callers
    in the same integration or core module are searched. Returns None when
    there are none, when one of them can't be resolved, or when the integration
    or module defines more than one function with this name, since calls are
    matched by name.
    """
    found = (
        find_parameter(func, version_arg.id)
        if isinstance(version_arg, ast.Name)
        else None
    )
    parameter = version_arg.id if found and isinstance(version_arg, ast.Name) else None
    definitions = sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == func.name
        for _, _, tree in files
        for node in ast.walk(tree)
    )
    if definitions > 1:
        return None
    index, default = found or (None, None)
    positional = [*func.args.posonlyargs, *func.args.args]
    is_method = bool(positional) and positional[0].arg in ("self", "cls")
    # The issue id can be forwarded from the callers too.
    issue_parameter = (
        find_parameter(func, issue_arg.id) if isinstance(issue_arg, ast.Name) else None
    )
    issue = None if issue_parameter else issue_id(issue_arg, constants, func_file)
    items = []
    for rel, text, tree in files:
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call):
                continue
            if isinstance(call.func, ast.Name) and call.func.id == func.name:
                shift = 0
            elif isinstance(call.func, ast.Attribute) and call.func.attr == func.name:
                shift = 1 if is_method else 0
            else:
                continue
            if parameter is None:
                version = resolve_version(version_arg, constants, func_file)
                source = f"{func.name}() {ast.unparse(version_arg)}"
            else:
                call_index = None if index is None else index - shift
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
            if issue_parameter and isinstance(issue_arg, ast.Name):
                issue = forwarded_issue_id(
                    call,
                    issue_arg.id,
                    issue_parameter,
                    shift,
                    rel,
                    func_file,
                    constants,
                )
            items.append(Item(rel, call.lineno, version, source, issue))
    return items or None


def forwarded_issue_id(
    call: ast.Call,
    name: str,
    parameter: tuple[int | None, ast.expr | None],
    shift: int,
    file: str,
    func_file: str,
    constants: Constants,
) -> str | None:
    """Return the repair issue id a caller passes to a helper."""
    index, default = parameter
    argument = passed_argument(call, name, None if index is None else index - shift)
    if argument is False:
        return issue_id(default, constants, func_file)
    return issue_id(argument, constants, file)


def area_of(file: str) -> tuple[str, str]:
    """Return the integration or core module of a file, and its kind."""
    parts = file.split("/")
    if parts[1] == "components":
        return parts[2], "integration"
    return "/".join(parts[1:]), "core"


def slugify(text: str) -> str:
    """Return text as a branch name part."""
    return re.sub(r"[^a-z0-9_]+", "-", text.lower()).strip("-")


def branch_name(name: str, version: str, suffix: str | None = None) -> str:
    """Return the cleanup branch name for a deprecation."""
    branch = f"deprecation-cleanup/{slugify(name.removesuffix('.py'))}-{version}"
    return f"{branch}-{slugify(suffix)}" if suffix else branch


def _deprecation_order(
    key: tuple[str, str, str | None],
) -> tuple[str, int, int, str]:
    """Sort deprecations by name, version and issue id."""
    major, minor = key[1].split(".")
    return key[0], int(major), int(minor), key[2] or ""


def scan(root: Path, current: tuple[int, int]) -> dict[str, Any]:
    """Find the deprecations under root/homeassistant that are due at current."""
    files = [
        (path, path.relative_to(root).as_posix())
        for path in sorted((root / "homeassistant").rglob("*.py"))
    ]
    markers = (KEY, ENUM_METACLASS, *POSITIONAL)
    candidates = set()
    for path, rel in files:
        text = path.read_text()
        if any(marker in text for marker in markers):
            candidates.add(rel)
    # Constants and callers are only resolved within an integration or module,
    # so only those with a candidate file need to be parsed.
    areas = {area_of(rel)[0] for rel in candidates}
    trees: dict[str, tuple[str, ast.Module]] = {}
    area_files: dict[str, list[tuple[str, str, ast.Module]]] = {}
    constants = Constants()
    for path, rel in files:
        if (name := area_of(rel)[0]) not in areas:
            continue
        text = path.read_text()
        tree = ast.parse(text)
        constants.add(rel, module_constants(tree))
        area_files.setdefault(name, []).append((rel, text, tree))
        if rel in candidates:
            trees[rel] = (text, tree)

    deprecations: dict[tuple[str, str, str | None], Deprecation] = {}
    unresolved: list[Item] = []
    passthrough: list[Item] = []
    for rel, (text, tree) in trees.items():
        name, kind = area_of(rel)
        owners = enclosing_functions(tree)
        for value, call in find_values(tree):
            if isinstance(value, ast.Constant) and value.value is None:
                continue
            issue_arg = issue_argument(call)
            issue = issue_id(issue_arg, constants, rel)
            item = Item(
                rel,
                value.lineno,
                None,
                ast.get_source_segment(text, value) or "",
                issue,
            )
            fixed = isinstance(value, ast.Constant) or (
                isinstance(value, ast.Name) and value.id.isupper()
            )
            func = owners.get(value)
            # A helper's callers can pass the version, the issue id, or both.
            forwards_issue = (
                func is not None
                and isinstance(issue_arg, ast.Name)
                and find_parameter(func, issue_arg.id) is not None
            )
            if (
                func is not None
                and (forwards_issue or not fixed)
                and (
                    callers := caller_items(
                        func, rel, value, issue_arg, area_files[name], constants
                    )
                )
                is not None
            ):
                items = callers
            elif fixed:
                item.version = resolve_version(value, constants, rel)
                items = [item]
            else:
                # A variable or attribute forwarded from outside this integration or module.
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
                deprecations.setdefault(
                    (name, version, found.issue_id),
                    Deprecation(
                        name,
                        kind,
                        version,
                        found.issue_id,
                        branch_name(name, version, found.issue_id),
                    ),
                ).items.append(found)

    return {
        "current_version": f"{current[0]}.{current[1]}",
        "deprecations": [
            asdict(deprecations[key])
            for key in sorted(deprecations, key=_deprecation_order)
        ],
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
