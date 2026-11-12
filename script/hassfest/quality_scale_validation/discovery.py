"""Enforce that the integration supports discovery.

https://contributors.home-assistant.io/core/quality-scale/discovery/
"""

import ast

from hassfest import ast_parse_module
from hassfest.model import Config, Integration

MANIFEST_KEYS = [
    "bluetooth",
    "dhcp",
    "homekit",
    "lorawan",
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


def _has_discovery_matcher(integration: Integration, key: str) -> bool:
    """Test if the manifest has a matcher that can discover new devices.

    DHCP matchers with only `registered_devices` are used to keep the address
    of already configured devices up to date and do not discover new devices.
    """
    if not (matchers := integration.manifest.get(key)):
        return False
    if key != "dhcp":
        return True
    return any(set(matcher) - {"registered_devices"} for matcher in matchers)


def _has_discovery_function(module: ast.Module, steps: set[str]) -> bool:
    """Test if the module defines at least one of the discovery functions."""
    return any(
        type(item) is ast.AsyncFunctionDef and item.name in steps
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
    if any(_has_discovery_matcher(integration, key) for key in MANIFEST_KEYS):
        return None

    # Fallback => check config_flow step
    steps = CONFIG_FLOW_STEPS
    if integration.manifest.get("dhcp"):
        # Only registered_devices matchers, the DHCP step can only update
        # already configured devices.
        steps = steps - {"async_step_dhcp"}
    config_flow = ast_parse_module(config_flow_file)
    if not _has_discovery_function(config_flow, steps):
        return [f"Integration is missing one of {steps} in {config_flow_file}"]

    return None
