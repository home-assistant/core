"""Enforce that the integration uses ConfigEntry.runtime_data to store runtime data.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/runtime-data
"""

import ast

from script.hassfest.model import Integration


def _has_attribute_access(tree: ast.AST, node_name: str, attribute_name: str) -> bool:
    """Check if a node with the specified attribute is accessed."""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == node_name
            and node.attr == attribute_name
        ):
            return True
    return False


def validate(integration: Integration) -> list[str] | None:
    """Validate that the integration uses ConfigEntry.runtime_data to store runtime data."""
    init_file = integration.path / "__init__.py"
    init = ast.parse(init_file.read_text())

    for item in init.body:
        if isinstance(item, ast.AsyncFunctionDef) and item.name == "async_setup_entry":
            if len(item.args.args) != 2:
                raise ValueError(
                    f"async_setup_entry in {init_file} has incorrect signature (expected 2 arguments)"
                )
            config_entry_arg = item.args.args[1].arg
            if not _has_attribute_access(item, config_entry_arg, "runtime_data"):
                return [
                    "Integration does not use ConfigEntry.runtime_data in async_setup_entry.",
                ]

    return None
