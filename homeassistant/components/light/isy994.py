"""
Support for ISY994 switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.isy994/
"""
import logging
from typing import Callable

from homeassistant.components.isy994 import filter_nodes
from homeassistant.components.light import Light
from homeassistant.components.isy994 import ISYDevice, NODES, ISY
from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNKNOWN
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

VALUE_TO_STATE = {
    False: STATE_OFF,
    True: STATE_ON,
}

UOM = ['2', '78']
STATES = [STATE_OFF, STATE_ON, 'true', 'false']


def setup_platform(hass, config: ConfigType,
                   add_devices: Callable[[list], None], discovery_info=None):
    """Set up the ISY994 light platform."""
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
    """Representation of an ISY994 light devie."""

    def __init__(self, node: object) -> None:
        """Initialize the ISY994 light device."""
        ISYDevice.__init__(self, node)

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 light is on."""
        return self.state == STATE_ON

    @property
    def state(self) -> str:
        """Get the state of the ISY994 light."""
        return VALUE_TO_STATE.get(bool(self.value), STATE_UNKNOWN)

    def turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 light device."""
        if not self._node.fastOff():
            _LOGGER.debug('Unable to turn on switch.')

    def turn_on(self, brightness=100, **kwargs) -> None:
        """Send the turn on command to the ISY994 light device."""
        if not self._node.on(val=brightness):
            _LOGGER.debug('Unable to turn on switch.')
