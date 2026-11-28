"""Diagnostics support for SMHI."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from .coordinator import SMHIConfigEntry

TO_REDACT = [
    CONF_LATITUDE,
    CONF_LONGITUDE,
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SMHIConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator, fire_coordinator = entry.runtime_data

    return async_redact_data(
        {
            "entry_data": entry.data,
            "current": coordinator.current,
            "fire_current": fire_coordinator.fire_current,
        },
        TO_REDACT,
    )
