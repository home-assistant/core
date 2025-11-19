"""Diagnostics platform for Senz integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import SENZConfigEntry

TO_REDACT = [
    "access_token",
    "refresh_token",
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SENZConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    raw_data = ([device.raw_data for device in entry.runtime_data.data.values()],)

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "thermostats": raw_data,
    }
