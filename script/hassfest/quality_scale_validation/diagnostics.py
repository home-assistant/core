"""Enforce that the integration implements diagnostics.

https://contributors.home-assistant.io/core/quality-scale/diagnostics/
"""

import ast

from hassfest import ast_parse_module
from hassfest.model import Config, Integration

DIAGNOSTICS_FUNCTIONS = {
    "async_get_config_entry_diagnostics",
    "async_get_device_diagnostics",
}


def _has_diagnostics_function(module: ast.Module) -> bool:
    """Test if the module defines at least one of the diagnostics functions."""
    return any(
        isinstance(item, ast.AsyncFunctionDef) and item.name in DIAGNOSTICS_FUNCTIONS
        for item in module.body
    )


def validate(
    config: Config, integration: Integration, *, rules_done: set[str]
) -> list[str] | None:
    """Validate that the integration implements diagnostics."""
    diagnostics_file = integration.path / "diagnostics.py"
    if not diagnostics_file.exists():
        return [
            "Integration does not implement diagnostics (is missing diagnostics.py)"
        ]

    if not _has_diagnostics_function(ast_parse_module(diagnostics_file)):
        return [
            f"Integration is missing one of {DIAGNOSTICS_FUNCTIONS} "
            f"in {diagnostics_file}"
        ]
    return None
