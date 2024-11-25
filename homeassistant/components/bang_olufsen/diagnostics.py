"""Support for Bang & Olufsen diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import BangOlufsenConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: BangOlufsenConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return {
        "websocket_connected": config_entry.runtime_data.client.websocket_connected,
        "config_entry": config_entry.as_dict(),
    }
