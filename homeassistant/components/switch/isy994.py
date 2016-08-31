"""
Support for ISY994 switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.isy994/
"""
import logging

from homeassistant.components.isy994 import filter_nodes
from homeassistant.components.switch import SwitchDevice, DOMAIN
from homeassistant.components.isy994 import (ISYDevice, NODES, PROGRAMS, ISY,
                                             KEY_ACTIONS, KEY_STATUS,
                                             GROUPS)
from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNKNOWN
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

VALUE_TO_STATE = {
    False: STATE_OFF,
    True: STATE_ON,
}

UOM = ['2', '78']
STATES = [STATE_OFF, STATE_ON, 'true', 'false']


def setup_platform(hass, config: ConfigType, add_devices, discovery_info=None):
    """
    Set up the ISY994 switch platform.

    :param hass: HomeAssistant.
    :param config: The platform configuration.
    :param add_devices: The add devices callback function.
    :param discovery_info: Discovery information
    :return: Whether the platform was set up correctly.
    """
    if ISY is None or not ISY.connected:
        _LOGGER.error('A connection has not been made to the ISY controller.')
        return False

    devices = []

    for node in filter_nodes(NODES, units=UOM,
                             states=STATES):
        if not node.dimmable:
            devices.append(ISYSwitchDevice(node))

    for node in GROUPS:
        devices.append(ISYSwitchDevice(node))

    for program in PROGRAMS.get(DOMAIN, []):
        try:
            status = program[KEY_STATUS]
            actions = program[KEY_ACTIONS]
            assert actions.dtype == 'program', 'Not a program'
        except (KeyError, AssertionError):
            pass
        else:
            devices.append(ISYSwitchProgram(program.name, status, actions))

    add_devices(devices)


class ISYSwitchDevice(ISYDevice, SwitchDevice):
    """Representation of an ISY994 switch device."""

    def __init__(self, node):
        """
        Initialize the ISY994 switch device.

        :param node: The ISY994 Node.
        """
        ISYDevice.__init__(self, node)

    @property
    def is_on(self) -> bool:
        """
        Get whether the ISY994 device is in the on state.

        :return: Whether the switch is in the on state.
        """
        return self.state == STATE_ON

    @property
    def state(self) -> str:
        """
        Get the state of the ISY994 device.

        :return: The state of the ISY994 switch.
        """
        return VALUE_TO_STATE.get(bool(self.value), STATE_UNKNOWN)

    def turn_off(self, **kwargs):
        """
        Send the turn on command to the ISY994 switch.

        :param kwargs: Keyword arguments.
        :return: None.
        """
        if not self._node.off():
            _LOGGER.debug('Unable to turn on switch.')

    def turn_on(self, **kwargs):
        """
        Send the turn off command to the ISY994 switch.

        :param kwargs: Keyword arguments.
        :return: None.
        """
        if not self._node.on():
            _LOGGER.debug('Unable to turn on switch.')


class ISYSwitchProgram(ISYSwitchDevice):
    """A representation of an ISY994 program switch."""

    def __init__(self, name, node, actions):
        """
        Initialize the ISY994 switch program

        :param name: The device name.
        :param node: The status program node.
        :param actions: The actions program node.
        """
        ISYSwitchDevice.__init__(self, node)
        self._name = name
        self._actions = actions

    @property
    def is_on(self) -> bool:
        """
        Get whether the ISY994 switch program is on.

        :return: Whether the ISY994 switch program is on.
        """
        return bool(self.value)

    def turn_on(self, **kwargs):
        """
        Send the turn on command to the ISY994 switch program.

        :param kwargs: Keyword arguments.
        :return: None.
        """
        if not self._actions.runThen():
            _LOGGER.error('Unable to turn on switch')

    def turn_off(self, **kwargs):
        """
        Send the turn off command to the ISY994 switch program.

        :param kwargs: Keyword arguments.
        :return: None.
        """
        if not self._actions.runElse():
            _LOGGER.error('Unable to turn off switch')
