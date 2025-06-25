"""Diagnostics support for Sensor.Community."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from .const import CONF_SENSOR_ID, DOMAIN
from .coordinator import LuftdatenDataUpdateCoordinator

TO_REDACT = {
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SENSOR_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: LuftdatenDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    return async_redact_data(coordinator.data, TO_REDACT)
