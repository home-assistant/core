"""Diagnostics support for Nanoleaf."""
from __future__ import annotations

from typing import Any

from aionanoleaf import Nanoleaf

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    device: Nanoleaf = hass.data[DOMAIN][config_entry.entry_id].device

    return {
        "info": async_redact_data(config_entry.as_dict(), (CONF_TOKEN, "title")),
        "data": {
            "brightness_max": device.brightness_max,
            "brightness_min": device.brightness_min,
            "brightness": device.brightness,
            "color_mode": device.color_mode,
            "color_temperature_max": device.color_temperature_max,
            "color_temperature_min": device.color_temperature_min,
            "color_temperature": device.color_temperature,
            "effect": device.effect,
            "effects_list": device.effects_list,
            "firmware_version": device.firmware_version,
            "hue_max": device.hue_max,
            "hue_min": device.hue_min,
            "hue": device.hue,
            "is_on": device.is_on,
            "manufacturer": device.manufacturer,
            "port": device.port,
            "saturation_max": device.saturation_max,
            "saturation_min": device.saturation_min,
            "saturation": device.saturation,
            "serial_no": device.serial_no,
        },
    }
