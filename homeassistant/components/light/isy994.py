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
    """
    Set up the ISY994 light platform.

    :param hass: HomeAssistant.
    :param config: Platform configuration.
    :param add_devices: The add devices callback method.
    :param discovery_info: The discovery information.
    :return: Whether the platform was set up properly.
    """
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
    """
    Representation of an ISY994 light devie.
    """

    def __init__(self, node):
        """
        Initialize the ISY994 light device.

        :param node: The ISY994 node.
        """
        ISYDevice.__init__(self, node)

    @property
    def is_on(self) -> bool:
        """
        Get whether the ISY994 light is on.

        :return: Whether the ISY994 light is in the 'on' state
        """
        return self.state == STATE_ON

    @property
    def state(self) -> str:
        """
        Get the state of the ISY994 light.

        :return: The state of the ISY994 light device.
        """
        return VALUE_TO_STATE.get(self.value, STATE_UNKNOWN)

    def turn_off(self, **kwargs):
        """
        Send the turn off command to the ISY994 light device.

        :param kwargs: Keyword Arguments.
        :return: None.
        """
        if not self._node.fastOff():
            _LOGGER.debug('Unable to turn on switch.')

    def turn_on(self, brightness=100, **kwargs):
        """
        Send the turn on command to the ISY994 light device.

        :param kwargs: Keyword arguments.
        :return: None.
        """
        if not self._node.on(val=brightness):
            _LOGGER.debug('Unable to turn on switch.')
