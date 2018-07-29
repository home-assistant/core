"""
Support for Velbus Binary Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.velbus/
"""
import asyncio
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.velbus import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['velbus']


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up Velbus binary sensors."""
    if discovery_info == None:
        return
    sensors = []
    for sensor in discovery_info:
        module = hass.data[DOMAIN].get_module(sensor[0])
        channel = sensor[1]
        sensors.append(VelbusBinarySensor(module, channel))
    async_add_devices(sensors, update_before_add=True)


class VelbusBinarySensor(BinarySensorDevice):
    """Representation of a Velbus Binary Sensor."""

    def __init__(self, module, channel):
        """Initialize a Velbus light."""
        self._module = module
        self._channel = channel

    async def async_added_to_hass(self):
        """Add listener for state changes."""
        def _init_velbus():
            """Initialize Velbus on startup."""
            self._module.on_status_update(self._channel, self._on_update)
        await self.hass.async_add_job(_init_velbus)

    def _on_update(self, state):
        self.schedule_update_ha_state()

    async def async_update(self):
        """Update module status."""
        future = self.hass.loop.create_future()

        def callback():
            self.hass.add_job(future.set_result, None)

        self._module.load(callback)

        await future

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the display name of this sensor."""
        return self._module.get_name(self._channel)

    @property
    def is_on(self):
        """Return true if the sensor is on."""
        return self._module.is_closed(self._channel)
