"""
Support for Velbus switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.velbus/
"""
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.components.velbus import (DOMAIN, VelbusEntity)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['velbus']


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the Velbus Switch platform."""
    if discovery_info is None:
        return
    switches = []
    for switch in discovery_info:
        module = hass.data[DOMAIN].get_module(switch[0])
        channel = switch[1]
        switches.append(VelbusSwitch(module, channel, hass))
    async_add_devices(switches, update_before_add=False)


class VelbusSwitch(SwitchDevice, VelbusEntity):
    """Representation of a switch."""

    @property
    def unique_id(self):
        """Get unique ID."""
        return "{}-{}".format(self._module.serial, self._channel)

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
        """Return true if the switch is on."""
        return self._module.is_on(self._channel)

    def turn_on(self, **kwargs):
        """Instruct the switch to turn on."""
        self._module.turn_on(self._channel)

    def turn_off(self, **kwargs):
        """Instruct the switch to turn off."""
        self._module.turn_off(self._channel)

    async def async_added_to_hass(self):
        """Add listener for state changes."""
        await self.hass.async_add_job(self._init_velbus)

    async def async_update(self):
        """Update module status."""
        await self._load_module()

    def _init_velbus(self, callback):
        """Initialize Velbus on startup."""
        self._module.on_status_update(self._channel, callback)

    def _on_update(self, state):
        self.schedule_update_ha_state()

