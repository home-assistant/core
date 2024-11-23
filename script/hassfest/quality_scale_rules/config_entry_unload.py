"""Enforce that the integration has a config flow."""

import ast

from . import QualityScaleCheck


def _has_function(
    module: ast.Module, _type: ast.AsyncFunctionDef | ast.FunctionDef, name: str
) -> bool:
    """Test if the module defines a function."""
    return any(type(item) is _type and item.name == name for item in module.body)


def validate(check: QualityScaleCheck) -> None:
    """Validate that the integration has a config flow."""

    init_file = check.integration.path / "__init__.py"
    init = ast.parse(init_file.read_text())

    if not _has_function(init, ast.AsyncFunctionDef, "async_unload_entry"):
        check.add_error(
            "config_entry_unload",
            "Integration does not support config entry unloading (is missing async_unload_entry "
            "in __init__.py)",
        )
