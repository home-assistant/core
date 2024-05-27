"""Diagnostics support for bond."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import BondConfigEntry

TO_REDACT = {"access_token"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BondConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    hub = data.hub
    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
        },
        "hub": {
            "version": hub._version,  # noqa: SLF001
        },
        "devices": [
            {
                "device_id": device.device_id,
                "props": device.props,
                "attrs": device._attrs,  # noqa: SLF001
                "supported_actions": device._supported_actions,  # noqa: SLF001
            }
            for device in hub.devices
        ],
    }
