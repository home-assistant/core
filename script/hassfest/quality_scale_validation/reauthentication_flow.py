"""Enforce that the integration implements a reauthentication flow.

https://contributors.home-assistant.io/core/quality-scale/reauthentication-flow/
"""

import ast

from hassfest import ast_parse_module
from hassfest.model import Config, Integration


def _has_step_reauth_function(module: ast.Module) -> bool:
    """Test if the module defines `async_step_reauth`."""
    return any(
        isinstance(item, ast.AsyncFunctionDef) and item.name == "async_step_reauth"
        for item in ast.walk(module)
    )


def validate(
    config: Config, integration: Integration, *, rules_done: set[str]
) -> list[str] | None:
    """Validate that the integration has a reauthentication flow."""
    config_flow_file = integration.path / "config_flow.py"
    if not config_flow_file.exists():
        return ["Integration is missing config_flow.py"]

    if not _has_step_reauth_function(ast_parse_module(config_flow_file)):
        return [
            "Integration does not support a reauthentication flow "
            f"(is missing `async_step_reauth` in {config_flow_file})"
        ]
    return None
