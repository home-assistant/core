"""
Support for XS1 sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/xs1/
"""

import asyncio
import logging

from homeassistant.helpers.entity import Entity

from ..xs1 import DOMAIN, SENSORS, XS1DeviceEntity

DEPENDENCIES = ['xs1']
_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = ['temperature']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the sensor platform."""

    _LOGGER.debug("initializing XS1 Sensor")

    sensors = hass.data[DOMAIN][SENSORS]

    _LOGGER.debug("Adding Sensor devices...")

    for sensor in sensors:
        async_add_devices([XS1Sensor(sensor)])


class XS1Sensor(XS1DeviceEntity, Entity):
    """Representation of a Sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.device.name()

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.device.value()

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.device.unit()
