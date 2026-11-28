"""Enforce that the integration prevents duplicates from being configured.

https://contributors.home-assistant.io/core/quality-scale/unique-config-entry/
"""

import ast

from hassfest import ast_parse_module
from hassfest.model import Config, Integration

from . import has_base_class


def _has_method_call(module: ast.Module, name: str) -> bool:
    """Test if the module calls a specific method."""
    return any(
        type(item.func) is ast.Attribute and item.func.attr == name
        for item in ast.walk(module)
        if isinstance(item, ast.Call)
    )


def _has_abort_entries_match(module: ast.Module) -> bool:
    """Test if the module calls `_async_abort_entries_match`."""
    return _has_method_call(module, "_async_abort_entries_match")


def _has_infrared_consumer_duplicate_check(module: ast.Module) -> bool:
    """Test if the module relies on the infrared consumer duplicate check.

    The default user step of the infrared consumer config flow does the check,
    so a module that defines its own user step must call it.
    """
    if not has_base_class(module, {"InfraredConsumerConfigFlow"}):
        return False
    defines_step_user = any(
        isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name == "async_step_user"
        for item in ast.walk(module)
    )
    if not defines_step_user:
        return True
    return _has_method_call(module, "_async_abort_infrared_entities_match")


def _has_abort_unique_id_configured(module: ast.Module) -> bool:
    """Test if the module calls defines (and checks for) a unique_id."""
    return _has_method_call(module, "async_set_unique_id") and _has_method_call(
        module, "_abort_if_unique_id_configured"
    )


def validate(
    config: Config, integration: Integration, *, rules_done: set[str]
) -> list[str] | None:
    """Validate that the integration prevents duplicate devices."""

    if integration.manifest.get("single_config_entry"):
        return None

    config_flow_file = integration.path / "config_flow.py"
    config_flow = ast_parse_module(config_flow_file)

    if not (
        _has_abort_entries_match(config_flow)
        or _has_infrared_consumer_duplicate_check(config_flow)
        or _has_abort_unique_id_configured(config_flow)
    ):
        return [
            "Integration doesn't prevent the same device or service from being "
            f"set up twice in {config_flow_file}"
        ]
    return None
