"""
Support for XS1 sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/xs1/
"""

import logging

from homeassistant.helpers.entity import Entity

from ..xs1 import DOMAIN, SENSORS, XS1DeviceEntity

DEPENDENCIES = ['xs1']
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Setup the sensor platform."""

    _LOGGER.debug("initializing XS1 Sensor")

    sensors = hass.data[DOMAIN][SENSORS]

    _LOGGER.debug("Adding Sensor devices...")

    sensor_entities = []
    for sensor in sensors:
        sensor_entities.append(XS1Sensor(sensor))

    async_add_devices(sensor_entities)


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
