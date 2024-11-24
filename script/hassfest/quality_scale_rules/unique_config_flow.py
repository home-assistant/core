"""Enforce that the integration prevents duplicate devices."""

import ast

from . import QualityScaleCheck


def _has_function_call(module: ast.Module, name: str) -> bool:
    """Test if the module defines a function."""
    for item in ast.walk(module):
        if not isinstance(item, ast.Call):
            continue
        if isinstance(item.func, ast.Attribute) and item.func.attr == name:
            return True
    return False


def validate(check: QualityScaleCheck) -> None:
    """Validate that the integration prevents duplicate devices."""

    config_flow_file = check.integration.path / "config_flow.py"
    config_flow = ast.parse(config_flow_file.read_text())

    if (
        _has_function_call(config_flow, "async_set_unique_id")
        and _has_function_call(config_flow, "_abort_if_unique_id_configured")
    ) or (_has_function_call(config_flow, "_async_abort_entries_match")):
        return
    check.add_error(
        "unique-config-flow",
        "Integration doesn't prevent the same device or service to be able to be set up twice "
        "(is missing async_set_unique_id, _abort_if_unique_id_configured or "
        "_async_abort_entries_match function calls in config_flow)",
    )
