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

    if not _defines_runtime_data_on_setup(init):
        return [
            "Integration does not define entry.runtime_data in async_setup_entry",
        ]

    return None
