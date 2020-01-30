"""Support for Abode Security System sensors."""
import logging

import abodepy.helpers.constants as CONST

from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
)

from . import AbodeDevice
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Sensor types: Name, icon
SENSOR_TYPES = {
    CONST.TEMP_STATUS_KEY: ["Temperature", DEVICE_CLASS_TEMPERATURE],
    CONST.HUMI_STATUS_KEY: ["Humidity", DEVICE_CLASS_HUMIDITY],
    CONST.LUX_STATUS_KEY: ["Lux", DEVICE_CLASS_ILLUMINANCE],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Abode sensor devices."""
    data = hass.data[DOMAIN]

    entities = []

    for device in data.abode.get_devices(generic_type=CONST.TYPE_SENSOR):
        for sensor_type in SENSOR_TYPES:
            if sensor_type not in device.get_value(CONST.STATUSES_KEY):
                continue
            entities.append(AbodeSensor(data, device, sensor_type))

    async_add_entities(entities)


class AbodeSensor(AbodeDevice):
    """A sensor implementation for Abode devices."""

    def __init__(self, data, device, sensor_type):
        """Initialize a sensor for an Abode device."""
        super().__init__(data, device)
        self._sensor_type = sensor_type
        self._name = "{0} {1}".format(
            self._device.name, SENSOR_TYPES[self._sensor_type][0]
        )
        self._device_class = SENSOR_TYPES[self._sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def unique_id(self):
        """Return a unique ID to use for this device."""
        return f"{self._device.device_uuid}-{self._sensor_type}"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._sensor_type == CONST.TEMP_STATUS_KEY:
            return self._device.temp
        if self._sensor_type == CONST.HUMI_STATUS_KEY:
            return self._device.humidity
        if self._sensor_type == CONST.LUX_STATUS_KEY:
            return self._device.lux

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        if self._sensor_type == CONST.TEMP_STATUS_KEY:
            return self._device.temp_unit
        if self._sensor_type == CONST.HUMI_STATUS_KEY:
            return self._device.humidity_unit
        if self._sensor_type == CONST.LUX_STATUS_KEY:
            return self._device.lux_unit
