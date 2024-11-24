"""Enforce that the integration has a reconfiguration flow.


"""

import ast

from . import QualityScaleCheck


def _has_function(module: ast.Module, name: str) -> bool:
    """Test if the module defines a function."""
    for item in ast.walk(module):
        if (
            isinstance(item, (ast.AsyncFunctionDef, ast.FunctionDef))
        ) and item.name == name:
            return True
    return False


def validate(check: QualityScaleCheck) -> None:
    """Validate that the integration has a reconfiguration flow.

    This checks for the existence of an explicit `async_step_reconfigure` step,
    but integrations may also support reconfiguration through an options flow.
    The options flow may or may not support reconfiguration, but we can't tell.
    """

    config_flow_file = check.integration.path / "config_flow.py"
    config_flow = ast.parse(config_flow_file.read_text())

    if not _has_function(config_flow, "async_step_reconfigure") and not _has_function(
        config_flow, "async_get_options_flow"
    ):
        check.add_error(
            "reconfiguration-flow",
            "Integration does not support a reconfiguration flow (is missing "
            "async_step_reconfigure or an async_get_options_flow that supports "
            "reconfiguration)",
        )
