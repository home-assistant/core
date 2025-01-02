"""Enforce that the integration supports discovery.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/discovery/
"""

import ast

from script.hassfest import ast_parse_module
from script.hassfest.model import Config, Integration

MANIFEST_KEYS = [
    "bluetooth",
    "dhcp",
    "homekit",
    "mqtt",
    "ssdp",
    "usb",
    "zeroconf",
]
CONFIG_FLOW_STEPS = {
    "async_step_bluetooth",
    "async_step_discovery",
    "async_step_dhcp",
    "async_step_hassio",
    "async_step_homekit",
    "async_step_mqtt",
    "async_step_ssdp",
    "async_step_usb",
    "async_step_zeroconf",
}


def _has_discovery_function(module: ast.Module) -> bool:
    """Test if the module defines at least one of the discovery functions."""
    return any(
        type(item) is ast.AsyncFunctionDef and item.name in CONFIG_FLOW_STEPS
        for item in ast.walk(module)
    )


def validate(
    config: Config, integration: Integration, *, rules_done: set[str]
) -> list[str] | None:
    """Validate that the integration implements diagnostics."""

    config_flow_file = integration.path / "config_flow.py"
    if not config_flow_file.exists():
        return ["Integration is missing config_flow.py"]

    # Check manifest
    if any(key in integration.manifest for key in MANIFEST_KEYS):
        return None

    # Fallback => check config_flow step
    config_flow = ast_parse_module(config_flow_file)
    if not (_has_discovery_function(config_flow)):
        return [
            f"Integration is missing one of {CONFIG_FLOW_STEPS} "
            f"in {config_flow_file}"
        ]

    return None
