"""Diagnostics support for Schlage."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import SchlageDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: SchlageDataUpdateCoordinator = config_entry.runtime_data
    # NOTE: Schlage diagnostics are already redacted.
    return {
        "locks": [ld.lock.get_diagnostics() for ld in coordinator.data.locks.values()]
    }
