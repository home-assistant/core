"""Diagnostics support for Bring."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from . import BringConfigEntry
from .coordinator import BringData


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: BringConfigEntry
) -> dict[str, BringData]:
    """Return diagnostics for a config entry."""

    return config_entry.runtime_data.data
