"""Diagnostics support for WMS WebControl pro API integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diag = {
        "control": entry.runtime_data.__dict__,
        "dests": {k: v.__dict__ for k, v in entry.runtime_data.dests.items()},
        "rooms": {k: v.__dict__ for k, v in entry.runtime_data.rooms.items()},
        "scenes": {k: v.__dict__ for k, v in entry.runtime_data.scenes.items()},
    }
    for dest in diag["dests"].values():
        dest["actions"] = {k: v.__dict__ for k, v in dest["_actions"].items()}
    return diag
