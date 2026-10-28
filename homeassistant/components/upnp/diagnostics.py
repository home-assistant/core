"""Diagnostics support for UPnP/IGD."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import (
    CONFIG_ENTRY_LOCATION,
    CONFIG_ENTRY_MAC_ADDRESS,
    CONFIG_ENTRY_ORIGINAL_UDN,
    CONFIG_ENTRY_UDN,
    ROUTER_IP,
)
from .coordinator import UpnpConfigEntry

TO_REDACT = {
    CONFIG_ENTRY_LOCATION,
    CONFIG_ENTRY_MAC_ADDRESS,
    CONFIG_ENTRY_ORIGINAL_UDN,
    CONFIG_ENTRY_UDN,
    ROUTER_IP,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: UpnpConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    device = coordinator.device
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "entry_options": dict(entry.options),
        "device": {
            "manufacturer": device.manufacturer,
            "model_name": device.model_name,
            "device_type": device.device_type,
            "force_poll": device.force_poll,
        },
        "data": async_redact_data(coordinator.data, TO_REDACT),
    }
