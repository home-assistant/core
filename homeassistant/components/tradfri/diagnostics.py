"""Diagnostics support for IKEA Tradfri."""

from __future__ import annotations

from typing import Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_GATEWAY_ID, COORDINATOR, COORDINATOR_LIST, DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics the Tradfri platform."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator_data = entry_data[COORDINATOR]

    device_registry = dr.async_get(hass)
    device = cast(
        dr.DeviceEntry,
        device_registry.async_get_device(
            identifiers={(DOMAIN, entry.data[CONF_GATEWAY_ID])}
        ),
    )

    device_data: list = [
        coordinator.device.device_info.model_number
        for coordinator in coordinator_data[COORDINATOR_LIST]
    ]

    return {
        "gateway_version": device.sw_version,
        "device_data": sorted(device_data),
    }
