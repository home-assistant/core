"""
Support for Velbus Binary Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.velbus/
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.velbus import (DOMAIN, VelbusEntity)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['velbus']


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up Velbus binary sensors."""
    if discovery_info is None:
        return
    sensors = []
    for sensor in discovery_info:
        module = hass.data[DOMAIN].get_module(sensor[0])
        channel = sensor[1]
        sensors.append(VelbusBinarySensor(module, channel, hass))
    async_add_devices(sensors, update_before_add=False)


class VelbusBinarySensor(BinarySensorDevice, VelbusEntity):
    """Representation of a Velbus Binary Sensor."""

    @property
    def unique_id(self):
        serial = 0
        if self._module.serial == 0:
            serial = self._module.get_module_address()
        else:
            serial = self._module.serial
        return "{}-{}".format(serial, self._channel)

    @property
    def name(self):
        """Return the display name of this entity."""
        return self._module.get_name(self._channel)

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def is_on(self):
        """Return true if the sensor is on."""
        return self._module.is_closed(self._channel)

    async def async_added_to_hass(self):
        """Add listener for state changes."""
        await self.hass.async_add_job(self._init_velbus)

    async def async_update(self):
        """Update module status."""
        await self._load_module()
