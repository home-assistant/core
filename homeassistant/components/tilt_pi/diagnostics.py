"""Diagnostics for the Tilt Pi integration."""

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import TiltPiConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TiltPiConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return {
        "entry_data": entry.data,
        "data": entry.runtime_data.data,
    }
