"""Diagnostics support for RDW."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import RDWConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RDWConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: dict[str, Any] = entry.runtime_data.data.to_dict()
    return data
