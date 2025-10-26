"""Diagnostics support for Devialet."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import DevialetConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DevialetConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return await entry.runtime_data.client.async_get_diagnostics()
