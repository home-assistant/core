"""Diagnostics support for Mawaqit."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from .types import MawaqitConfigEntry, MawaqitData

TO_REDACT = [
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: MawaqitConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    mawaqit_data: MawaqitData = config_entry.runtime_data

    return {
        "config_entry_data": async_redact_data(config_entry.data, TO_REDACT),
        "mosque_data": mawaqit_data.mosque_coordinator.data,
        "prayer_times_data": mawaqit_data.prayer_time_coordinator.data,
    }
