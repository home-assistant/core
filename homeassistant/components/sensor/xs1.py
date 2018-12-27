"""
Support for XS1 sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.xs1/
"""

import logging

from homeassistant.components.xs1 import (
    DOMAIN as COMPONENT_DOMAIN, SENSORS, XS1DeviceEntity)
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['xs1']
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the XS1 sensor platform."""
    sensors = hass.data[COMPONENT_DOMAIN][SENSORS]

    sensor_entities = []
    for sensor in sensors:
        sensor_entities.append(XS1Sensor(sensor))

    async_add_entities(sensor_entities)


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
