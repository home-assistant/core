"""Diagnostics platform for Senz integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = [
    "access_token",
    "refresh_token",
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    raw_data = (
        [device.raw_data for device in hass.data[DOMAIN][entry.entry_id].data.values()],
    )

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "thermostats": raw_data,
    }
