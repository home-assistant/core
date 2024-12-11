"""Enforce that the integration prevents duplicates from being configured.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/unique-config-entry/
"""

import ast

from script.hassfest import ast_parse_module
from script.hassfest.model import Config, Integration


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
        or _has_abort_unique_id_configured(config_flow)
    ):
        return [
            "Integration doesn't prevent the same device or service from being "
            f"set up twice in {config_flow_file}"
        ]
    return None
