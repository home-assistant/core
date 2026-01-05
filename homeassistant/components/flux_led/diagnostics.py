"""Diagnostics support for flux_led."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import FluxLedConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FluxLedConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
        },
        "data": entry.runtime_data.device.diagnostics,
    }
