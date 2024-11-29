"""Enforce that the integration uses ConfigEntry.runtime_data to store runtime data.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/runtime-data
"""

import ast

from script.hassfest.model import Integration


def _sets_runtime_data(
    async_setup_entry_function: ast.AsyncFunctionDef, config_entry_argument: ast.arg
) -> bool:
    """Check that `entry.runtime` gets set within `async_setup_entry`."""
    for node in ast.walk(async_setup_entry_function):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == config_entry_argument.arg
            and node.attr == "runtime_data"
            and isinstance(node.ctx, ast.Store)
        ):
            return True
    return False


def _get_setup_entry_function(module: ast.Module) -> ast.AsyncFunctionDef | None:
    """Get async_setup_entry function."""
    for item in module.body:
        if isinstance(item, ast.AsyncFunctionDef) and item.name == "async_setup_entry":
            return item
    return None


def validate(integration: Integration) -> list[str] | None:
    """Validate correct use of ConfigEntry.runtime_data."""
    init_file = integration.path / "__init__.py"
    init = ast.parse(init_file.read_text())

    # Should not happen, but better to be safe
    if not (async_setup_entry := _get_setup_entry_function(init)):
        return [f"Could not find `async_setup_entry` in {init_file}"]
    if len(async_setup_entry.args.args) != 2:
        return [f"async_setup_entry has incorrect signature in {init_file}"]
    config_entry_argument = async_setup_entry.args.args[1]

    if not _sets_runtime_data(async_setup_entry, config_entry_argument):
        return [
            "Integration does not set entry.runtime_data in async_setup_entry"
            f"({init_file})"
        ]

    return None
