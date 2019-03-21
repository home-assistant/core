"""Support for Velbus sensors."""
import logging

from . import DOMAIN as VELBUS_DOMAIN, VelbusEntity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['velbus']


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Velbus temp sensor platform."""
    if discovery_info is None:
        return
    sensors = []
    for sensor in discovery_info:
        module = hass.data[VELBUS_DOMAIN].get_module(sensor[0])
        channel = sensor[1]
        sensors.append(VelbusSensor(module, channel))
    async_add_entities(sensors)


class VelbusSensor(VelbusEntity):
    """Representation of a sensor."""

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._module.get_class(self._channel)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._module.get_state(self._channel)

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._module.get_unit(self._channel)
