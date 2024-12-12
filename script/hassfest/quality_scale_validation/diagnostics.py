"""Enforce that the integration implements diagnostics.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/diagnostics/
"""

import ast

from script.hassfest import ast_parse_module
from script.hassfest.model import Config, Integration

DIAGNOSTICS_FUNCTIONS = {
    "async_get_config_entry_diagnostics",
    "async_get_device_diagnostics",
}


def _has_diagnostics_function(module: ast.Module) -> bool:
    """Test if the module defines at least one of diagnostic functions."""
    return any(
        type(item) is ast.AsyncFunctionDef and item.name in DIAGNOSTICS_FUNCTIONS
        for item in ast.walk(module)
    )


def validate(
    config: Config, integration: Integration, *, rules_done: set[str]
) -> list[str] | None:
    """Validate that the integration implements diagnostics."""

    diagnostics_file = integration.path / "diagnostics.py"
    if not diagnostics_file.exists():
        return [
            "Integration does implement diagnostics platform "
            "(is missing diagnostics.py)",
        ]

    diagnostics = ast_parse_module(diagnostics_file)

    if not _has_diagnostics_function(diagnostics):
        return [
            f"Integration is missing one of {DIAGNOSTICS_FUNCTIONS} "
            f"in {diagnostics_file}"
        ]

    return None
