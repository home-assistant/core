"""Diagnostics support for the Nature Remo integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from .coordinator import NatureRemoConfigEntry

TO_REDACT = {CONF_API_TOKEN, "mac_address", "bt_mac_address", "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NatureRemoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return async_redact_data(
        {
            "entry_data": entry.data,
            "rate_limit": asdict(coordinator.client.rate_limit),
            "devices": [asdict(device) for device in coordinator.data.devices.values()],
            "appliances": [
                asdict(appliance) for appliance in coordinator.data.appliances.values()
            ],
        },
        TO_REDACT,
    )
