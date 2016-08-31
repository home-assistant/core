"""
Support for ISY994 switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.isy994/
"""
import logging

from homeassistant.components.isy994 import filter_nodes
from homeassistant.components.light import Light, DOMAIN
from homeassistant.components.isy994 import (ISYDevice, NODES, PROGRAMS, ISY,
                                             KEY_ACTIONS, KEY_STATUS)
from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNKNOWN
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

VALUE_TO_STATE = {
    0: STATE_OFF,
    100: STATE_ON,
    False: STATE_OFF,
    True: STATE_ON,
}

UOM = ['2', '78']
STATES = [STATE_OFF, STATE_ON, 'true', 'false']


def setup_platform(hass, config: ConfigType, add_devices, discovery_info=None):
    """Setup the ISY platform."""

    if ISY is None or not ISY.connected:
        _LOGGER.error('A connection has not been made to the ISY controller.')
        return False

    devices = []

    for node in filter_nodes(NODES, units=UOM,
                             states=STATES):
        if node.dimmable:
            devices.append(ISYLightDevice(node))

    add_devices(devices)


class ISYLightDevice(ISYDevice, Light):
    """Representation of a ISY switch."""

    def __init__(self, node):
        """Initialize the binary sensor."""
        ISYDevice.__init__(self, node)

    @property
    def is_on(self) -> bool:
        """Return true if device is locked."""
        return self.state == STATE_ON

    @property
    def state(self) -> str:
        """Return the state of the device."""
        return VALUE_TO_STATE.get(self.value, STATE_UNKNOWN)

    def turn_off(self, **kwargs):
        """Turn off the switch."""
        if not self._node.fastOff():
            _LOGGER.debug('Unable to turn on switch.')

    def turn_on(self, **kwargs):
        """Turn on the switch."""
        brightness = kwargs.get('brightness', 100)
        if not self._node.on(val=brightness):
            _LOGGER.debug('Unable to turn on switch.')
