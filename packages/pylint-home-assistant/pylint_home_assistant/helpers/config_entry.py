"""Helpers for typed config entries, such as ``ConfigEntry[MyRuntimeData]``."""

from functools import cache
from pathlib import Path

import astroid
from astroid import nodes


def is_config_entry(node: nodes.NodeNG | None) -> bool:
    """Return True for a reference to ``ConfigEntry`` itself."""
    match node:
        case nodes.Name(name="ConfigEntry") | nodes.Attribute(attrname="ConfigEntry"):
            return True
    return False


def is_typed_config_entry(node: nodes.NodeNG) -> bool:
    """Return True for ``ConfigEntry[...]``."""
    match node:
        case nodes.Subscript(value=value) if is_config_entry(value):
            return True
    return False


@cache
def typed_config_entries(integration_dir: Path) -> tuple[str, ...]:
    """Return the names of the typed config entries an integration defines."""
    names: set[str] = set()
    for source in integration_dir.rglob("*.py"):
        try:
            module = astroid.parse(source.read_text())
        except astroid.exceptions.AstroidSyntaxError, OSError:
            continue
        for node in module.body:
            match node:
                # type MyConfigEntry = ConfigEntry[MyCoordinator]
                case nodes.TypeAlias(name=nodes.AssignName(name=name), value=value) if (
                    is_typed_config_entry(value)
                ):
                    names.add(name)
                # MyConfigEntry = ConfigEntry[MyCoordinator]
                case nodes.Assign(
                    targets=[nodes.AssignName(name=name)], value=value
                ) if is_typed_config_entry(value):
                    names.add(name)
    return tuple(sorted(names))
