"""Enforce that the integration implements reconfiguration flow.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reconfiguration-flow/
"""

import ast

from script.hassfest.model import Integration


def _has_step_reconfigure_function(module: ast.Module) -> bool:
    """Test if the module defines a function."""
    return any(
        type(item) is ast.AsyncFunctionDef and item.name == "async_step_reconfigure"
        for item in ast.walk(module)
    )


def validate(integration: Integration) -> list[str] | None:
    """Validate that the integration has a reconfiguration flow."""

    config_flow_file = integration.path / "config_flow.py"
    config_flow = ast.parse(config_flow_file.read_text())

    if not _has_step_reconfigure_function(config_flow):
        return [
            "Integration does not support a reconfiguration flow "
            f"(is missing `async_step_reconfigure` in {config_flow_file})"
        ]
    return None
