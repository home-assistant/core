"""Enforce that the integration has a reauthentication flow."""

import ast

from . import QualityScaleCheck


def _has_async_function(module: ast.Module, name: str) -> bool:
    """Test if the module defines a function."""
    return any(
        type(item) is ast.AsyncFunctionDef and item.name == name
        for item in ast.walk(module)
    )


def validate(check: QualityScaleCheck) -> None:
    """Validate that the integration has a reauthentication flow."""

    config_flow_file = check.integration.path / "config_flow.py"
    config_flow = ast.parse(config_flow_file.read_text())

    if not _has_async_function(
        config_flow, "async_step_reauth"
    ) or not _has_async_function(config_flow, "async_step_reauth_confirm"):
        check.add_error(
            "reauthentication-flow",
            "Integration does not support a reconfiguration flow (is missing async_step_reauth or async_step_reauth_confirm)",
        )
