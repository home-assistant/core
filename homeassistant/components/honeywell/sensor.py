"""Support for Honeywell (US) Total Connect Comfort sensors."""
from __future__ import annotations
from homeassistant.components.honeywell.const import DOMAIN
from homeassistant.helpers.typing import ConfigType
from homeassistant.core import HomeAssistant

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)

_LOGGER = logging.getLogger(__name__)

def setup_platform(
    hass: HomeAssistant, config: ConfigType, add_entities, discovery_info=None
) -> None:
    """Set up the Honeywell thermostat."""
    device = hass.data[DOMAIN]["device"]
    sensors = []

    if device.outdoor_temperature != None:
        sensors.append(HoneywellUSSensor(device, "temperature"))
    if device.outdoor_humidity != None:
        sensors.append(HoneywellUSSensor(device, "humidity"))

    add_entities(sensors)

class HoneywellUSSensor(SensorEntity):
    """Representation of a Honeywell US Sensor."""

    def __init__(
        self, device, sensor_type
    ):
        """Initialize the sensor."""
        self._device = device

        self._name = f"{device.name} outdoor {sensor_type}"
        self._type = sensor_type

        _LOGGER.debug("latestData = %s ", device._data)

    @property
    def name(self):
        """Return the name of the Honeywell US Sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        if self._type in (DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE):
            return self._type
        return None

    @property
    def state(self):
        """Return the state of the sensor."""

        if self._type == "temperature":
            return self.outdoor_temperature

        return self.outdoor_humidity

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        if self._type == "temperature":
            return TEMP_CELSIUS if self._device.temperature_unit == "C" else TEMP_FAHRENHEIT

        return PERCENTAGE

    @property
    def outdoor_humidity(self) -> int | None:
        """Return the current outdoor humidity."""
        return self._device.outdoor_humidity

    @property
    def outdoor_temperature(self) -> float | None:
        """Return the current outdoor temperature."""
        return self._device.outdoor_temperature