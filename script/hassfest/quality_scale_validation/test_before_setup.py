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

# Helpers that raise one of the above on the caller's behalf, so an integration
# awaiting them satisfies the rule without repeating the mapping itself.
_VALID_AWAITED_CALLS = {
    "async_config_entry_first_refresh",
    "async_ensure_token_valid",
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

    if isinstance(expression, ast.Subscript):
        # Raise errors[0][0]
        # Unable to determine exception name
        return None

    raise AssertionError(
        f"Raise is neither Attribute nor Call nor Name: {type(expression)}"
    )


def _raises_exception(integration: Integration) -> bool:
    """Check that a valid exception is raised."""
    # Sorted to ensure reproducible checks
    for module_file in sorted(integration.path.rglob("*.py")):
        module = ast_parse_module(module_file)
        for node in ast.walk(module):
            if (
                isinstance(node, ast.Raise)
                and _get_exception_name(node.exc) in _VALID_EXCEPTIONS
            ):
                return True

    return False


def _awaits_raising_helper(async_setup_entry_function: ast.AsyncFunctionDef) -> bool:
    """Check that `async_setup_entry` awaits a helper that raises on its behalf.

    The call only has to sit somewhere inside an await, so gathering several of
    them still counts, while an unawaited call does not.
    """
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _VALID_AWAITED_CALLS
        for await_node in ast.walk(async_setup_entry_function)
        if isinstance(await_node, ast.Await)
        for node in ast.walk(await_node)
    )


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

    if not (
        _awaits_raising_helper(async_setup_entry) or _raises_exception(integration)
    ):
        return [f"Integration does not raise one of {_VALID_EXCEPTIONS}"]
    return None
