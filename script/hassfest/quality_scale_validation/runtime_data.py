"""Enforce that the integration uses ConfigEntry.runtime_data to store runtime data.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/runtime-data
"""

import ast

from script.hassfest.model import Integration


def _sets_attribute(tree: ast.AST, node_name: str, attribute_name: str) -> bool:
    """Check that an attribute is set on a node within the tree."""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == node_name
            and node.attr == attribute_name
            and isinstance(node.ctx, ast.Store)
        ):
            return True
    return False


def _sets_runtime_data_on_setup(init: ast.AST, filename: str) -> bool:
    """Check if the integration sets entry.runtime_data in async_setup_entry."""
    for item in init.body:
        if not (
            isinstance(item, ast.AsyncFunctionDef) and item.name == "async_setup_entry"
        ):
            continue
        if len(item.args.args) != 2:
            raise ValueError(
                f"async_setup_entry in {filename} has incorrect signature (expected 2 arguments)"
            )
        config_entry_arg = item.args.args[1].arg
        return _sets_attribute(item, config_entry_arg, "runtime_data")
    return False


def validate(integration: Integration) -> list[str] | None:
    """Validate that the integration uses ConfigEntry.runtime_data to store runtime data."""
    init_file = integration.path / "__init__.py"
    init = ast.parse(init_file.read_text())

    if not _sets_runtime_data_on_setup(init, init_file):
        return [
            "Integration does not set entry.runtime_data in async_setup_entry",
        ]

    return None
