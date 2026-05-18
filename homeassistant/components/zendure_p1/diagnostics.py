"""Diagnostics support for Zendure Smart Meter P1."""

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from . import ZendureP1ConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ZendureP1ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return asdict(entry.runtime_data.data)
