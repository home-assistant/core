"""Provides diagnostics for EcoWitt."""

from __future__ import annotations

from typing import Any

from aioecowitt import EcoWittListener

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    ecowitt: EcoWittListener = hass.data[DOMAIN][entry.entry_id]
    station_id = next(item[1] for item in device.identifiers if item[0] == DOMAIN)

    station = ecowitt.stations[station_id]

    return {
        "device": {
            "name": station.station,
            "model": station.model,
            "frequency": station.frequence,  # codespell:ignore frequence
            "version": station.version,
        },
        "raw": ecowitt.last_values[station_id],
        "sensors": {
            sensor.key: sensor.value
            for sensor in ecowitt.sensors.values()
            if sensor.station.key == station_id
        },
    }
