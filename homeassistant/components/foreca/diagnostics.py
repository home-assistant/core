"""Diagnostics support for Foreca."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from .coordinator import ForecaConfigEntry

TO_REDACT = {CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ForecaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = config_entry.runtime_data.data

    return {
        "config_entry_data": async_redact_data(dict(config_entry.data), TO_REDACT),
        "current": asdict(data.current),
        "hourly": [asdict(hour) for hour in data.hourly],
        "daily": [asdict(day) for day in data.daily],
        "air_quality": asdict(data.air_quality) if data.air_quality else None,
        "air_quality_daily": [asdict(day) for day in data.air_quality_daily],
    }
