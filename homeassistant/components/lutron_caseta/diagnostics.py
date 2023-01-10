"""Diagnostics support for lutron_caseta."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .models import LutronCasetaData


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: LutronCasetaData = hass.data[DOMAIN][entry.entry_id]
    bridge = data.bridge
    return {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
        },
        "bridge_data": {
            "devices": bridge.devices,
            "buttons": bridge.buttons,
            "scenes": bridge.scenes,
            "occupancy_groups": bridge.occupancy_groups,
            "areas": bridge.areas,
        },
        "integration_data": {
            "keypad_button_names_to_leap": data.keypad_data.button_names_to_leap,
            "keypad_buttons": data.keypad_data.buttons,
            "keypads": data.keypad_data.keypads,
        },
    }
