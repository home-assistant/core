"""Enforce that the integration supports discovery.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/discovery/
"""

import ast

from script.hassfest.model import Integration

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


def _has_discovery_function(module: ast.Module) -> bool:
    """Test if the module defines at least one of the discovery functions."""
    return any(
        type(item) is ast.AsyncFunctionDef and item.name in DISCOVERY_FUNCTIONS
        for item in ast.walk(module)
    )


def validate(integration: Integration) -> list[str] | None:
    """Validate that the integration implements diagnostics."""

    config_flow_file = integration.path / "config_flow.py"
    if not config_flow_file.exists():
        return ["Integration is missing config_flow.py"]

    config_flow = ast.parse(config_flow_file.read_text())

    if not _has_discovery_function(config_flow):
        return [
            f"Integration is missing one of {DISCOVERY_FUNCTIONS} "
            f"in {config_flow_file}"
        ]

    return None
