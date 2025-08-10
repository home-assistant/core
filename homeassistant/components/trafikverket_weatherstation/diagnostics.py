"""Diagnostics support for Trafikverket Weatherstation."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from . import TVWeatherConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TVWeatherConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for Trafikverket Weatherstation config entry."""
    return asdict(entry.runtime_data.data)
