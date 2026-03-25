"""Diagnostics support for Syncthru."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import SyncThruConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SyncThruConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return entry.runtime_data.data.raw()
