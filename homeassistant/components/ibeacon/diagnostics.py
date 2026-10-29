"""Diagnostics support for iBeacon Tracker."""

from typing import Any

from homeassistant.core import HomeAssistant

from . import IBeaconConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IBeaconConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return entry.runtime_data.async_get_diagnostics()
