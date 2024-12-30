"""Diagnostics support for Nord Pool."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from . import TVWeatherConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TVWeatherConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for Nord Pool config entry."""
    return asdict(entry.runtime_data.data)
