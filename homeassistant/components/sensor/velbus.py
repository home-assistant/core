"""
Velbus sensors.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/sensor.velbus/
"""
import logging

from homeassistant.const import (
    TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE)
from homeassistant.components.velbus import (
    DOMAIN as VELBUS_DOMAIN, VelbusEntity)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['velbus']


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Velbus temp sensor platform."""
    if discovery_info is None:
        return
    sensors = []
    for sensor in discovery_info:
        module = hass.data[VELBUS_DOMAIN].get_module(sensor[0])
        channel = sensor[1]
        sensors.append(VelbusTempSensor(module, channel))
    async_add_entities(sensors)


class VelbusTempSensor(VelbusEntity):
    """Representation of a temperature sensor."""

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_TEMPERATURE

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._module.getCurTemp()

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return TEMP_CELSIUS
