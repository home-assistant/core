"""Enforce that the integration raises correctly during initialisation.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/test-before-setup/
"""

import ast

from script.hassfest.model import Integration

_VALID_EXCEPTIONS = {
    "ConfigEntryNotReady",
    "ConfigEntryAuthFailed",
    "ConfigEntryError",
}


def _raises_exception(async_setup_entry_function: ast.AsyncFunctionDef) -> bool:
    """Check that a valid exception is raised within `async_setup_entry`."""
    for node in ast.walk(async_setup_entry_function):
        if isinstance(node, ast.Raise):
            if isinstance(node.exc, ast.Name) and node.exc.id in _VALID_EXCEPTIONS:
                return True
            if isinstance(node.exc, ast.Call) and node.exc.func.id in _VALID_EXCEPTIONS:
                return True

    return False


def _calls_first_refresh(async_setup_entry_function: ast.AsyncFunctionDef) -> bool:
    """Check that a async_config_entry_first_refresh within `async_setup_entry`."""
    for node in ast.walk(async_setup_entry_function):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "async_config_entry_first_refresh"
        ):
            return True

    return False


def _get_setup_entry_function(module: ast.Module) -> ast.AsyncFunctionDef | None:
    """Get async_setup_entry function."""
    for item in module.body:
        if isinstance(item, ast.AsyncFunctionDef) and item.name == "async_setup_entry":
            return item
    return None


def validate(integration: Integration) -> list[str] | None:
    """Validate correct use of ConfigEntry.runtime_data."""
    init_file = integration.path / "__init__.py"
    init = ast.parse(init_file.read_text())

    # Should not happen, but better to be safe
    if not (async_setup_entry := _get_setup_entry_function(init)):
        return [f"Could not find `async_setup_entry` in {init_file}"]

    if not (
        _raises_exception(async_setup_entry) or _calls_first_refresh(async_setup_entry)
    ):
        return [
            f"Integration does not raise one of {_VALID_EXCEPTIONS} "
            f"in async_setup_entry ({init_file})"
        ]
    return None
