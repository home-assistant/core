"""
EcoPlugs Component for aut-discovering Wion and EcoPlugs automatically

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/ecoplug/
"""

import logging

from datetime import timedelta

from homeassistant.const import (DEVICE_DEFAULT_NAME, EVENT_HOMEASSISTANT_STOP)
from homeassistant.components.switch import SwitchDevice

DEFAULT_INVERT_LOGIC = False

DOMAIN = 'ecoplug'
REQUIREMENTS = ['pyecoplug==0.0.5']
_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=5)


class EcoPlugSwitch(SwitchDevice):
    """Return the polling state."""
    def __init__(self, plug):
        """Initialize the switch."""
        self._plug = plug
        self._name = plug.name or DEVICE_DEFAULT_NAME
        self._state = self._plug.is_on()

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

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
        self.update()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._plug.turn_off()
        self.update()

    def update(self):
        """Update the switch's status."""
        _LOGGER.info('update')
        self._state = self._plug.is_on()


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up EcoPlug switches."""
    from pyecoplug import EcoDiscovery

    discovered = {}
    def add(plug):
        """Find switches on the network."""
        if plug.name not in discovered:
            add_devices([EcoPlugSwitch(plug)])
            discovered[plug.name] = plug

    def remove(plug):
        """Is there a way to remove devices??"""
        pass

    disco = EcoDiscovery(add, remove)
    disco.start()

    def stop_disco(event):
        disco.stop()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_disco)
