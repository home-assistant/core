"""
Support for ISY994 fans.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/fan.isy994/
"""
import logging

from homeassistant.components.isy994 import filter_nodes
from homeassistant.components.fan import (FanEntity, DOMAIN, SPEED_OFF,
                                          SPEED_LOW, SPEED_MED,
                                          SPEED_HIGH)
from homeassistant.components.isy994 import (ISYDevice, NODES, PROGRAMS, ISY,
                                             KEY_ACTIONS, KEY_STATUS)
from homeassistant.const import STATE_UNKNOWN, STATE_ON, STATE_OFF
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

VALUE_TO_STATE = {
    0: SPEED_OFF,
    63: SPEED_LOW,
    64: SPEED_LOW,
    190: SPEED_MED,
    191: SPEED_MED,
    255: SPEED_HIGH,
}

STATE_TO_VALUE = {}
for key in VALUE_TO_STATE:
    STATE_TO_VALUE[VALUE_TO_STATE[key]] = key

STATES = [SPEED_OFF, SPEED_LOW, SPEED_MED, SPEED_HIGH]


def setup_platform(hass, config: ConfigType, add_devices, discovery_info=None):
    """
    Setup the ISY994 fan platform.

    :param hass: HomeAsistant.
    :param config: The platform configuration.
    :param add_devices: The add devices callback method.
    :param discovery_info: The discovery information.
    :return: Whether the platform was setup properly.
    """
    if ISY is None or not ISY.connected:
        _LOGGER.error('A connection has not been made to the ISY controller.')
        return False

    devices = []

    for node in filter_nodes(NODES, states=STATES):
        devices.append(ISYFanDevice(node))

    for program in PROGRAMS.get(DOMAIN, []):
        try:
            status = program[KEY_STATUS]
            actions = program[KEY_ACTIONS]
            assert actions.dtype == 'program', 'Not a program'
        except (KeyError, AssertionError):
            pass
        else:
            devices.append(ISYFanProgram(program.name, status, actions))

    add_devices(devices)


class ISYFanDevice(ISYDevice, FanEntity):
    """Representation of an ISY994 fan device."""

    def __init__(self, node):
        """
        Initialize the ISY994 fan device.

        :param node: The ISY994 node.
        """
        ISYDevice.__init__(self, node)
        self.speed = self.state

    @property
    def state(self) -> str:
        """
        Get the state of the ISY994 fan device.

        :return: The state of the ISY994 fan device.
        """
        return VALUE_TO_STATE.get(self.value, STATE_UNKNOWN)

    def set_speed(self, speed: str) -> None:
        """
        Send the set speed command to the ISY994 fan device.

        :param speed: The speed to send to the device.
        :return: None.
        """
        if not self._node.on(val=STATE_TO_VALUE.get(speed, 0)):
            _LOGGER.debug('Unable to set fan speed')
        else:
            self.speed = self.state

    def turn_on(self, speed: str=None, **kwargs) -> None:
        """
        Send the turn on command to the ISY994 fan device.

        :param speed: The speed to set it to.
        :param kwargs: Keyword arguments.
        :return: None.
        """
        self.set_speed(speed)

    def turn_off(self, **kwargs) -> None:
        """
        Send the turn off command to the ISY994 fan device.

        :param kwargs: Keyword arguments.
        :return: None.
        """
        if not self._node.off():
            _LOGGER.debug('Unable to set fan speed')
        else:
            self.speed = self.state


class ISYFanProgram(ISYFanDevice):
    """Representation of an ISY994 fan program."""

    def __init__(self, name, node, actions):
        """
        Initialize the ISY994 fan program.

        :param name: The name of the ISY994 fan.
        :param node: The ISY994 program to get the status.
        :param actions: The ISY994 program to send commands.
        """
        ISYFanDevice.__init__(self, node)
        self._name = name
        self._actions = actions
        self.speed = STATE_ON if self.is_on else STATE_OFF

    @property
    def is_on(self) -> bool:
        """
        Get whether the ISY994 fan program is on.

        :return: Whether the ISY994 fan program is in the 'on' state.
        """
        return bool(self.value)

    @property
    def state(self):
        """
        Get the state of the ISY994 fan program.

        :return: The state of the ISY994 fan program.
        """
        return STATE_ON if self.is_on else STATE_OFF

    def turn_off(self, **kwargs):
        """
        Send the turn on command to ISY994 fan program.

        :param kwargs: Keyword arguments.
        :return: None.
        """
        if not self._actions.runThen():
            _LOGGER.error('Unable to open the cover')
        else:
            self.speed = STATE_ON if self.is_on else STATE_OFF

    def turn_on(self, **kwargs):
        """
        Send the turn off command to ISY994 fan program.

        :param kwargs: Keyword arguments.
        :return: None.
        """
        if not self._actions.runElse():
            _LOGGER.error('Unable to close the cover')
        else:
            self.speed = STATE_ON if self.is_on else STATE_OFF
