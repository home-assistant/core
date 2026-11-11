"""Enforce that the integration creates devices.

https://contributors.home-assistant.io/core/quality-scale/devices/
"""

import ast

from hassfest import ast_parse_module
from hassfest.model import Config, Integration

_DEVICE_INFO_CALLS = {
    "DeviceInfo",
    "sensor_device_info_to_hass_device_info",
}


def _call_name(node: ast.Call) -> str | None:
    """Return the name of the called function or method."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _creates_device(module: ast.Module) -> bool:
    """Test if the module provides device info or registers a device."""
    for node in ast.walk(module):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in _DEVICE_INFO_CALLS:
                return True
            # device_registry.async_get_or_create(config_entry_id=..., ...)
            if name == "async_get_or_create" and any(
                keyword.arg == "config_entry_id" for keyword in node.keywords
            ):
                return True
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "_attr_device_info"
            and isinstance(node.ctx, ast.Store)
        ):
            return True
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and any(
            isinstance(target, ast.Name) and target.id == "_attr_device_info"
            for target in (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
        ):
            return True
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "device_info"
        ):
            return True
    return False


def validate(
    config: Config, integration: Integration, *, rules_done: set[str]
) -> list[str] | None:
    """Validate that the integration creates devices."""
    # Sorted to ensure reproducible checks
    for module_file in sorted(integration.path.rglob("*.py")):
        if _creates_device(ast_parse_module(module_file)):
            return None

    return [
        "Integration does not create any devices "
        "(no `DeviceInfo`, `_attr_device_info` or `device_info` found)"
    ]
