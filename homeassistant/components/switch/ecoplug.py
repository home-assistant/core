# """
# EcoPlugs Component for auto-discovering Wion and EcoPlugs. No setup necessary.

# For more details about this platform, please refer to the documentation
# https://home-assistant.io/components/ecoplug/
# """

import logging
from datetime import timedelta

from homeassistant.const import (DEVICE_DEFAULT_NAME, ATTR_HIDDEN, EVENT_TIME_CHANGED, EVENT_HOMEASSISTANT_STOP)
from homeassistant.components.switch import SwitchDevice
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.event import track_time_change

DEFAULT_INVERT_LOGIC = False

DOMAIN = 'ecoplug'
REQUIREMENTS = ['pyecoplug==0.0.5']
_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)

class EcoPlugSwitch(SwitchDevice):
    def __init__(self, plug):
        self._plug = plug
        self._name = plug.name
        self._state = self._plug.is_on()

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        return self._name

    @property
    def is_on(self):
        return self._state

    def turn_on(self):
        self._plug.turn_on()
        self.update()

    def turn_off(self):
        self._plug.turn_off()
        self.update()

    def update(self):
        _LOGGER.info('update')
        self._state = self._plug.is_on()


def setup_platform(hass, config, add_devices, discovery_info=None):
    from pyecoplug import EcoDiscovery

    discovered = {}
    def add(plug):
        if not plug.name in discovered:
            add_devices([EcoPlugSwitch(plug)])
            discovered[plug.name] = plug

    def remove(plug):
        # Is there a way to remove devices??
        pass

    disco = EcoDiscovery(add, remove)
    disco.start()

    def stop_disco(event):
        disco.stop()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_disco)
