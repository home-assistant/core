"""Diagnostics support for Uhoo."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .coordinator import UhooConfigEntry

TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: UhooConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "config_entry": async_redact_data(entry.data, TO_REDACT),
        "devices": {
            serial: {
                "device_name": device.device_name,
                "serial_number": device.serial_number,
                "mac_address": device.mac_address,
                "temperature": device.temperature,
                "humidity": device.humidity,
                "co": device.co,
                "co2": device.co2,
                "pm25": device.pm25,
                "tvoc": device.tvoc,
                "no2": device.no2,
                "ozone": device.ozone,
                "air_pressure": device.air_pressure,
                "virus_index": device.virus_index,
                "mold_index": device.mold_index,
                "influenza_index": device.influenza_index,
            }
            for serial, device in coordinator.data.items()
        },
    }
