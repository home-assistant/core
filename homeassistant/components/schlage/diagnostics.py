"""Diagnostics support for Schlage."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SchlageDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: SchlageDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    locks = [lock_data.lock for lock_data in coordinator.data.locks.values()]
    # NOTE: Schalge diagnostics are already redacted.
    return {"locks": [lock.get_diagnostics() for lock in locks]}
