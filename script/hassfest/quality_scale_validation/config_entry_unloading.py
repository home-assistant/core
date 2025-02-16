"""Enforce that the integration implements entry unloading.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-entry-unloading/
"""

import ast

from script.hassfest import ast_parse_module
from script.hassfest.model import Config, Integration


def _has_unload_entry_function(module: ast.Module) -> bool:
    """Test if the module defines `async_unload_entry` function."""
    return any(
        type(item) is ast.AsyncFunctionDef and item.name == "async_unload_entry"
        for item in module.body
    )


def validate(
    config: Config, integration: Integration, *, rules_done: set[str]
) -> list[str] | None:
    """Validate that the integration has a config flow."""

    init_file = integration.path / "__init__.py"
    init = ast_parse_module(init_file)

    if not _has_unload_entry_function(init):
        return [
            "Integration does not support config entry unloading "
            "(is missing `async_unload_entry` in __init__.py)"
        ]
    return None
