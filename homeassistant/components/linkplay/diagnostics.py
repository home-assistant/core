"""Diagnostics support for Linkplay."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import LinkPlayConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LinkPlayConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    return {"device_info": data.bridge.to_dict()}
