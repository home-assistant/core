"""Diagnostics support for Yale Smart Alarm."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import COORDINATOR, DOMAIN
from .coordinator import YaleDataUpdateCoordinator

TO_REDACT = {
    "address",
    "name",
    "mac",
    "device_id",
    "sensor_map",
    "lock_map",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: YaleDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]
    return async_redact_data(coordinator.data, TO_REDACT)
