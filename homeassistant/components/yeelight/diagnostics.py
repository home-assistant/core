"""Diagnostics support for Yeelight."""

from typing import Any

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from . import YeelightConfigEntry
from .const import CONF_DETECTED_MODEL

# Capabilities are raw SSDP headers which also hold the id and location
CAPABILITIES_TO_INCLUDE = ("model", "fw_ver", "support")


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: YeelightConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    device = entry.runtime_data
    return {
        "detected_model": entry.data.get(CONF_DETECTED_MODEL),
        "options": {
            key: value for key, value in entry.options.items() if key != CONF_NAME
        },
        "device": {
            "model": device.model,
            "type": device.type.name if device.type is not None else None,
            "available": device.available,
            "music_mode": device.bulb.music_mode,
            "is_nightlight_supported": device.is_nightlight_supported,
            "capabilities": {
                key: device.capabilities[key]
                for key in CAPABILITIES_TO_INCLUDE
                if key in device.capabilities
            },
            "properties": device.bulb.last_properties,
        },
    }
