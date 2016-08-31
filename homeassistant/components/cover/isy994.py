"""
Support for ISY994 covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.isy994/
"""
import logging

from homeassistant.components.cover import CoverDevice, DOMAIN
from homeassistant.components.isy994 import (ISYDevice, NODES, PROGRAMS, ISY,
                                             KEY_ACTIONS, KEY_STATUS,
                                             filter_nodes)
from homeassistant.const import STATE_OPEN, STATE_CLOSED, STATE_UNKNOWN
from homeassistant.helpers.typing import ConfigType


_LOGGER = logging.getLogger(__name__)

VALUE_TO_STATE = {
    0: STATE_CLOSED,
    101: STATE_UNKNOWN,
}

UOM = ['97']
STATES = [STATE_OPEN, STATE_CLOSED, 'closing', 'opening']


def setup_platform(hass, config: ConfigType, add_devices, discovery_info=None):
    """
    Setup the ISY994 cover platform.

    :param hass: HomeAssistant.
    :param config: Platform configuration.
    :param add_devices: The add devices callback method.
    :param discovery_info: The discovery information.
    :return: Whether the platform was setup properly.
    """
    if ISY is None or not ISY.connected:
        _LOGGER.error('A connection has not been made to the ISY controller.')
        return False

    devices = []

    for node in filter_nodes(NODES, units=UOM,
                             states=STATES):
        devices.append(ISYCoverDevice(node))

    for program in PROGRAMS.get(DOMAIN, []):
        try:
            status = program[KEY_STATUS]
            actions = program[KEY_ACTIONS]
            assert actions.dtype == 'program', 'Not a program'
        except (KeyError, AssertionError):
            pass
        else:
            devices.append(ISYCoverProgram(program.name, status, actions))

    add_devices(devices)


class ISYCoverDevice(ISYDevice, CoverDevice):
    """Representation of an ISY994 cover device."""

    def __init__(self, node):
        """
        Initialize the ISY994 cover device.

        :param node: The ISY994 node.
        """
        ISYDevice.__init__(self, node)

    @property
    def current_cover_position(self):
        """
        Get the current cover position.

        :return: The percentage value representing how closed the cover is.
        """
        return sorted((0, self.value, 100))[1]

    @property
    def is_closed(self) -> bool:
        """
        Get whether the ISY994 cover device is closed.

        :return: Whether the ISY994 cover device is in the 'closed' status.
        """
        return self.state == STATE_CLOSED

    @property
    def state(self) -> str:
        """
        Get the state of the ISY994 cover device.

        :return: The state of the ISY994 cover device.
        """
        return VALUE_TO_STATE.get(self.value, STATE_OPEN)

    def open_cover(self, **kwargs):
        """
        Send the open cover command to the ISY994 cover device.

        :param kwargs: Keyword arguments.
        :return: None.
        """
        if not self._node.on(val=100):
            _LOGGER.error('Unable to open the cover')

    def close_cover(self, **kwargs):
        """
        Send the close cover command to the ISY994 cover device.

        :param kwargs: Keyword arguments.
        :return: None.
        """
        if not self._node.off():
            _LOGGER.error('Unable to close the cover')


class ISYCoverProgram(ISYCoverDevice):
    """Representation of an ISY994 cover program."""

    def __init__(self, name, node, actions):
        """
        Initialize the ISY994 cover program.

        :param name: The name of the cover device.
        :param node: The status program to get the device status.
        :param actions: The actions program for the device.
        """
        ISYCoverDevice.__init__(self, node)
        self._name = name
        self._actions = actions

    @property
    def is_closed(self) -> bool:
        """
        Get whether the ISY994 cover program is closed.

        :return: Whether the ISY994 is closed.
        """
        return bool(self.value)

    @property
    def state(self):
        """
        Get the state of the ISY994 cover program.

        :return: The program state.
        """
        return STATE_CLOSED if self.is_closed else STATE_OPEN

    def open_cover(self, **kwargs):
        """
        Send the open cover command to the ISY994 cover program.

        :param kwargs: Keyword arguments.
        :return: None.
        """
        if not self._actions.runThen():
            _LOGGER.error('Unable to open the cover')

    def close_cover(self, **kwargs):
        """
        Send the close cover command to the ISY994 cover program.

        :param kwargs: Keyword arguments.
        :return: None.
        """
        if not self._actions.runElse():
            _LOGGER.error('Unable to close the cover')
