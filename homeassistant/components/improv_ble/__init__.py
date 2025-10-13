"""The Improv BLE integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.typing import ConfigType

from .const import PROVISIONING_FUTURES

_LOGGER = logging.getLogger(__name__)

__all__ = ["async_register_next_flow"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Improv BLE component."""
    hass.data[PROVISIONING_FUTURES] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up improv_ble from a config entry."""
    raise NotImplementedError


def async_register_next_flow(hass: HomeAssistant, ble_mac: str, flow_id: str) -> None:
    """Register a next flow for a provisioned device.

    Called by other integrations (e.g., ESPHome) when they discover a device
    that was provisioned via Improv BLE. If Improv BLE is waiting for this
    device, the Future will be resolved with the flow_id.

    Args:
        hass: Home Assistant instance
        ble_mac: Bluetooth MAC address of the provisioned device
        flow_id: Config flow ID to chain to

    """
    registry = hass.data.get(PROVISIONING_FUTURES, {})
    normalized_mac = format_mac(ble_mac)

    future = registry.get(normalized_mac)
    if not future:
        _LOGGER.debug(
            "No provisioning future found for %s (flow_id %s)",
            normalized_mac,
            flow_id,
        )
        return

    if future.done():
        _LOGGER.debug(
            "Future for %s already done, ignoring flow_id %s",
            normalized_mac,
            flow_id,
        )
        return

    _LOGGER.debug(
        "Resolving provisioning future for %s with flow_id %s",
        normalized_mac,
        flow_id,
    )
    future.set_result(flow_id)
