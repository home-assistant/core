"""
EcoPlugs Component for aut-discovering Wion and EcoPlugs automatically.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.ecoplug/
"""

import logging

from datetime import timedelta

from homeassistant.const import (DEVICE_DEFAULT_NAME, EVENT_HOMEASSISTANT_STOP)
from homeassistant.components.switch import SwitchDevice

DEFAULT_INVERT_LOGIC = False

REQUIREMENTS = ['pyecoplug==0.0.5']
_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=5)

DEVICE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(SCAN_INTERVAL, default=5):
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
    vol.Optional(CONF_AUTOMATIC_ADD, default=TRUE):  cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up EcoPlug switches."""
    from pyecoplug import EcoDiscovery
    discovered = hass.data

    def add(plug):
        """Find switches on the network."""
        if plug.name not in discovered:
            add_devices([EcoPlugSwitch(plug)])
            discovered[plug.name] = plug

    def remove(plug):
        """Remove switch from the list."""
        async_will_remove_from_hass([EcoPlugSwitch(plug)], True)
            
    disco = EcoDiscovery(add, remove)
    disco.start()

    def stop_disco(event):
        """Stop device discovery."""
        disco.stop()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_disco)


class EcoPlugSwitch(SwitchDevice):
    """Return the polling state."""

    def __init__(self, plug):
        """Initialize the switch."""
        self._plug = plug
        self._name = plug.name or DEVICE_DEFAULT_NAME
        self._state = None

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._plug.turn_on()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._plug.turn_off()

    def update(self):
        """Update the switch's status."""
        self._state = self._plug.is_on()
