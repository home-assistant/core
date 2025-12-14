"""Diagnostics support for Sensor.Community."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from .const import CONF_SENSOR_ID
from .coordinator import LuftdatenConfigEntry

TO_REDACT = {
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SENSOR_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LuftdatenConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return async_redact_data(coordinator.data, TO_REDACT)
