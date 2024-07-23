"""Diagnostics support for Utility Meter."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_TARIFF_SENSORS, DATA_UTILITY


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    tariff_sensors = []

    for sensor in hass.data[DATA_UTILITY][entry.entry_id][DATA_TARIFF_SENSORS]:
        restored_last_extra_data = await sensor.async_get_last_extra_data()

        tariff_sensors.append(
            {
                "name": sensor.name,
                "entity_id": sensor.entity_id,
                "extra_attributes": sensor.extra_state_attributes,
                "last_sensor_data": restored_last_extra_data,
            }
        )

    return {
        "config_entry": entry,
        "tariff_sensors": tariff_sensors,
    }
