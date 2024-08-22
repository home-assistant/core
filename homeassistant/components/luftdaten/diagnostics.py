"""Diagnostics support for Sensor.Community."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE

from .const import CONF_SENSOR_ID, DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

TO_REDACT = {
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SENSOR_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: DataUpdateCoordinator[dict[str, Any]] = hass.data[DOMAIN][
        entry.entry_id
    ]
    return async_redact_data(coordinator.data, TO_REDACT)
