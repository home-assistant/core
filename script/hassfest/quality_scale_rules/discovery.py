"""Enforce that the integration supports discovery."""

import ast

from . import QualityScaleCheck

DISCOVERY_FUNCTIONS = [
    "async_step_discovery",
    "async_step_bluetooth",
    "async_step_hassio",
    "async_step_homekit",
    "async_step_mqtt",
    "async_step_ssdp",
    "async_step_zeroconf",
    "async_step_dhcp",
    "async_step_usb",
]


def _has_function_call(module: ast.Module, name: str) -> bool:
    """Test if the module defines a function."""
    for item in ast.walk(module):
        if not isinstance(item, ast.Call):
            continue
        if isinstance(item.func, ast.Attribute) and item.func.attr == name:
            return True
    return False


def validate(check: QualityScaleCheck) -> None:
    """Validate that the integration supports discovery."""

    config_flow_file = check.integration.path / "config_flow.py"
    config_flow = ast.parse(config_flow_file.read_text())

    if not any(_has_function_call(config_flow, func) for func in DISCOVERY_FUNCTIONS):
        check.add_error(
            "discovery",
            "Integration doesn't support discovery (is missing config_flow functions ",
            DISCOVERY_FUNCTIONS,
        )
