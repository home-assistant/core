"""Enforce that the integration prevents duplicates from being configured.

https://contributors.home-assistant.io/core/quality-scale/unique-config-entry/
"""

import ast

from hassfest import ast_parse_module
from hassfest.model import Config, Integration


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


def _has_method_call_outside_entry_steps(node: ast.AST, name: str) -> bool:
    """Test if the node calls a method outside reauth and reconfigure steps.

    In those steps `async_set_unique_id_or_abort` checks for a unique ID
    mismatch, not for an entry that is already configured.
    """
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
        node.name.startswith(("async_step_reauth", "async_step_reconfigure"))
    ):
        return False
    if (
        isinstance(node, ast.Call)
        and type(node.func) is ast.Attribute
        and node.func.attr == name
    ):
        return True
    return any(
        _has_method_call_outside_entry_steps(child, name)
        for child in ast.iter_child_nodes(node)
    )


def _has_abort_unique_id_configured(module: ast.Module) -> bool:
    """Test if the module calls defines (and checks for) a unique_id."""
    return _has_method_call_outside_entry_steps(
        module, "async_set_unique_id_or_abort"
    ) or (
        _has_method_call(module, "async_set_unique_id")
        and _has_method_call(module, "_abort_if_unique_id_configured")
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
        or _has_abort_unique_id_configured(config_flow)
    ):
        return [
            "Integration doesn't prevent the same device or service from being "
            f"set up twice in {config_flow_file}"
        ]
    return None
