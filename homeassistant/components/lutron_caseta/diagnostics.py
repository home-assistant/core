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
            "keypads": data.keypads,
            "keypad_buttons": data.keypad_buttons,
            "keypad_button_names_to_leap": data.keypad_button_names_to_leap,
            "keypad_trigger_schemas": data.keypad_trigger_schemas,
            "dr_device_id_to_keypad": data.dr_device_id_to_keypad,
        },
    }
