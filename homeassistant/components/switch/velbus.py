"""
Support for Velbus switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.velbus/
"""

import asyncio
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.components.velbus import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['velbus']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Velbus Switch platform."""
    velbus = hass.data[DOMAIN]
    modules = velbus.get_modules('switch')
    for module in modules:
        for channel in range(1, module.number_of_channels() + 1):
            async_add_devices([VelbusSwitch(module, channel)], update_before_add=True)
    return True


class VelbusSwitch(SwitchDevice):
    """Representation of a switch."""

    def __init__(self, module, channel):
        """Initialize a Velbus switch."""
        self._module = module
        self._channel = channel

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Add listener for state changes."""
        def _init_velbus():
            """Initialize Velbus on startup."""
            self._module.on_status_update(self._channel, self._on_update)
        yield from self.hass.async_add_job(_init_velbus)

    def _on_update(self, state):
        self.schedule_update_ha_state()

    @asyncio.coroutine
    def async_update(self):

        future = self.hass.loop.create_future()

        def callback():
            future.set_result(None)

        self._module.load(callback)

        yield from future

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._module.get_name(self._channel)

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._module.is_on(self._channel)

    def turn_on(self, **kwargs):
        """Instruct the switch to turn on."""
        self._module.turn_on(self._channel)

    def turn_off(self, **kwargs):
        """Instruct the switch to turn off."""
        self._module.turn_off(self._channel)
