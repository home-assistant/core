"""Enforce that the integration raises correctly during initialisation.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/test-before-setup/
"""

import ast

from script.hassfest import ast_parse_module
from script.hassfest.model import Config, Integration

_VALID_EXCEPTIONS = {
    "ConfigEntryNotReady",
    "ConfigEntryAuthFailed",
    "ConfigEntryError",
}


def _get_exception_name(expression: ast.expr) -> str:
    """Get the name of the exception being raised."""
    if expression is None:
        # Bare raise
        return None

    if isinstance(expression, ast.Name):
        # Raise Exception
        return expression.id

    if isinstance(expression, ast.Call):
        # Raise Exception()
        return _get_exception_name(expression.func)

    if isinstance(expression, ast.Attribute):
        # Raise namespace.???
        return _get_exception_name(expression.value)

    raise AssertionError(
        f"Raise is neither Attribute nor Call nor Name: {type(expression)}"
    )


def _raises_exception(integration: Integration) -> bool:
    """Check that a valid exception is raised."""
    for module_file in integration.path.rglob("*.py"):
        module = ast_parse_module(module_file)
        for node in ast.walk(module):
            if (
                isinstance(node, ast.Raise)
                and _get_exception_name(node.exc) in _VALID_EXCEPTIONS
            ):
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


def validate(
    config: Config, integration: Integration, *, rules_done: set[str]
) -> list[str] | None:
    """Validate correct use of ConfigEntry.runtime_data."""
    init_file = integration.path / "__init__.py"
    init = ast_parse_module(init_file)

    # Should not happen, but better to be safe
    if not (async_setup_entry := _get_setup_entry_function(init)):
        return [f"Could not find `async_setup_entry` in {init_file}"]

    if not (_calls_first_refresh(async_setup_entry) or _raises_exception(integration)):
        return [f"Integration does not raise one of {_VALID_EXCEPTIONS}"]
    return None
