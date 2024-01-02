"""Support for Epion API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from epion import Epion

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPressure, UnitOfTemperature, CONCENTRATION_PARTS_PER_MILLION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SITE_ID, DATA_API_CLIENT, DOMAIN




async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add an Epion entry."""
    # Add the needed sensors to hass
    epionBase = hass.data[DOMAIN][entry.entry_id][DATA_API_CLIENT]

    entities = []
    current_data = epionBase.last_response
    for epion_device in current_data['devices']:
        # Keys are: deviceId, deviceName, locationId, lastMeasurement, co2, temperature, humidity, pressure
        entities.append(EpionSensor(epion_device, "co2"))

    async_add_entities(entities)


class EpionSensor(SensorEntity):
    """Representation of an Epion Air sensor."""

    def __init__(self, epion_base, epion_device, key) -> None:
        """Initialize an EpionSensor."""
        self._epion_base = epion_base
        self._epion_device = epion_device
        self._measurement_key = key
        _attr_name = "Epion Air Sensor Name"
        _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
        _attr_device_class = SensorDeviceClass.CO2
        _attr_state_class = SensorStateClass.MEASUREMENT
        _attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, epion_device['deviceId'])},
            manufacturer="Epion"
        )

    async def async_update(self) -> None:
        """Get the latest data from the Epion API and update the state."""
        await self._epion_base.async_update()
        myDevice = self._epion_base.device_data[self._epion_device['deviceId']]
        if not myDevice:
            return 0 # No data available

        measurement = myDevice[self._measurement_key]
        if not measurement:
            return 0 # No relevant measurement available

        return measurement
