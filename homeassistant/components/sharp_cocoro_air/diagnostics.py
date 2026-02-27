"""Diagnostics for the Sharp COCORO Air integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import SharpCocoroAirConfigEntry

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SharpCocoroAirConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "config_entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "devices": {
            device_id: asdict(device) for device_id, device in coordinator.data.items()
        },
    }
