"""Support for Velbus Binary Sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice

from . import DOMAIN as VELBUS_DOMAIN, VelbusEntity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['velbus']


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up Velbus binary sensors."""
    if discovery_info is None:
        return
    sensors = []
    for sensor in discovery_info:
        module = hass.data[VELBUS_DOMAIN].get_module(sensor[0])
        channel = sensor[1]
        sensors.append(VelbusBinarySensor(module, channel))
    async_add_entities(sensors)


class VelbusBinarySensor(VelbusEntity, BinarySensorDevice):
    """Representation of a Velbus Binary Sensor."""

    @property
    def is_on(self):
        """Return true if the sensor is on."""
        return self._module.is_closed(self._channel)
