"""Enforce that the integration implements reconfiguration flow.

https://contributors.home-assistant.io/core/quality-scale/reconfiguration-flow/
"""

import ast

from hassfest import ast_parse_module
from hassfest.model import Config, Integration


def _is_subentry_flow(class_def: ast.ClassDef) -> bool:
    """Test if the class is a config subentry flow handler."""
    return any("SubentryFlow" in ast.unparse(base) for base in class_def.bases)


def _has_step_reconfigure_function(module: ast.Module) -> bool:
    """Test if the config flow (not a subentry flow) defines the reconfigure step."""
    return any(
        type(item) is ast.AsyncFunctionDef and item.name == "async_step_reconfigure"
        for class_def in ast.walk(module)
        if isinstance(class_def, ast.ClassDef) and not _is_subentry_flow(class_def)
        for item in class_def.body
    )


def validate(
    config: Config, integration: Integration, *, rules_done: set[str]
) -> list[str] | None:
    """Validate that the integration has a reconfiguration flow."""

    config_flow_file = integration.path / "config_flow.py"
    if not config_flow_file.exists():
        return ["Integration is missing config_flow.py"]

    config_flow = ast_parse_module(config_flow_file)

    if not _has_step_reconfigure_function(config_flow):
        return [
            "Integration does not support a reconfiguration flow "
            f"(is missing `async_step_reconfigure` in {config_flow_file})"
        ]
    return None
