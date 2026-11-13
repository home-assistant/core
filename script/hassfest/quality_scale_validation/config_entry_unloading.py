"""Enforce that the integration supports config entry unloading.

https://contributors.home-assistant.io/core/quality-scale/config-entry-unloading/
"""

import ast

from hassfest import ast_parse_module
from hassfest.model import Config, Integration


def _has_unload_entry_function(module: ast.Module) -> bool:
    """Test if the module defines `async_unload_entry`."""
    return any(
        isinstance(item, ast.AsyncFunctionDef) and item.name == "async_unload_entry"
        for item in module.body
    )


def validate(
    config: Config, integration: Integration, *, rules_done: set[str]
) -> list[str] | None:
    """Validate that the integration supports config entry unloading."""
    init_file = integration.path / "__init__.py"
    if not init_file.exists():
        return [f"Integration is missing {init_file}"]

    if not _has_unload_entry_function(ast_parse_module(init_file)):
        return [
            "Integration does not support config entry unloading "
            f"(is missing `async_unload_entry` in {init_file})"
        ]
    return None
