"""Diagnostics support for SpaceAPI."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import SpaceAPIConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SpaceAPIConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "config_entry_data": dict(entry.data),
        "config_entry_options": dict(entry.options),
    }
