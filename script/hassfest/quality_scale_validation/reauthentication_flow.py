"""Enforce that the integration implements reauthentication flow.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reauthentication-flow/
"""

import ast

from script.hassfest.model import Integration


def _has_async_function(module: ast.Module, name: str) -> bool:
    """Test if the module defines a function."""
    return any(
        type(item) is ast.AsyncFunctionDef and item.name == name
        for item in ast.walk(module)
    )


def validate(integration: Integration) -> list[str] | None:
    """Validate that the integration has a reauthentication flow."""

    config_flow_file = integration.path / "config_flow.py"
    config_flow = ast.parse(config_flow_file.read_text())

    if not _has_async_function(config_flow, "async_step_reauth"):
        return [
            "Integration does not support a reauthentication flow "
            f"(is missing `async_step_reauth` in {config_flow_file})"
        ]
    return None
