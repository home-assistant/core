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

from .const import CONF_SITE_ID, DATA_API_CLIENT, DOMAIN, LOGGER




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
        entities.append(EpionSensor(epionBase, epion_device, "co2"))

    async_add_entities(entities)


class EpionSensor(SensorEntity):
    """Representation of an Epion Air sensor."""

    def __init__(self, epion_base, epion_device, key) -> None:
        """Initialize an EpionSensor."""
        self._epion_base = epion_base
        self._epion_device = epion_device
        self._measurement_key = key
        self._last_value = self.extract_value()
        self._attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
        self._attr_device_class = SensorDeviceClass.CO2
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, epion_device['deviceId'])},
            manufacturer="Epion",
            name=epion_device['deviceName']
        )

    @property
    def name(self):
        myDeviceId = self._epion_device['deviceId']
        if myDeviceId not in self._epion_base.device_data:
            if "deviceName" in self._epion_device:
                return self._epion_device["deviceName"]
            return f"Epion - {myDeviceId}"
        myDevice = self._epion_base.device_data[myDeviceId]
        return myDevice["deviceName"]

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return self._epion_device['deviceId']

    @property
    def native_value(self) -> float:
        """Return the value reported by the sensor."""
        return round(self._last_value, 1)

    def extract_value(self) -> float:
        myDeviceId = self._epion_device['deviceId']
        # LOGGER.info("Attempting update for %s, known sensors: %d", myDeviceId, len(self._epion_base.device_data))
        if myDeviceId not in self._epion_base.device_data:
            # LOGGER.error("Missing Epion device %s from %d sensors", myDeviceId, len(self._epion_base.device_data))
            return 0  # No data available, this can happen during startup or if the device (temporarily) stopped sending data

        myDevice = self._epion_base.device_data[myDeviceId]
        # if not myDevice:
        # return 0 # No data available

        if self._measurement_key not in myDevice:
            LOGGER.debug("Missing Epion metric %s from device %s", self._measurement_key, myDeviceId)
            return 0  # No relevant measurement available

        measurement = myDevice[self._measurement_key]
        LOGGER.info("Epion device %s data %f", myDeviceId, measurement)

        return measurement

    async def async_update(self) -> None:
        """Get the latest data from the Epion API and update the state."""
        await self._epion_base.async_update()
        self._last_value = self.extract_value()
