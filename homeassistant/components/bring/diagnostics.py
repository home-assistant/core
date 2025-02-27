"""Diagnostics support for Bring."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import BringConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: BringConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return {
        "data": {k: v.to_dict() for k, v in config_entry.runtime_data.data.items()},
        "lists": [lst.to_dict() for lst in config_entry.runtime_data.lists],
        "user_settings": config_entry.runtime_data.user_settings.to_dict(),
    }
