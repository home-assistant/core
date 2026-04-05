"""Diagnostics support for Guntamatic."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import GuntamaticConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GuntamaticConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry_data": dict(entry.data),
        "data": entry.runtime_data.coordinator.data,
    }
