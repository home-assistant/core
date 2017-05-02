"""
Support for ISY994 fans.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/fan.isy994/
"""
import logging
from typing import Callable

from homeassistant.components.fan import (FanEntity, DOMAIN, SPEED_OFF,
                                          SPEED_LOW, SPEED_MEDIUM,
                                          SPEED_HIGH)
import homeassistant.components.isy994 as isy
from homeassistant.const import STATE_UNKNOWN, STATE_ON, STATE_OFF
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

VALUE_TO_STATE = {
    0: SPEED_OFF,
    63: SPEED_LOW,
    64: SPEED_LOW,
    190: SPEED_MEDIUM,
    191: SPEED_MEDIUM,
    255: SPEED_HIGH,
}

STATE_TO_VALUE = {}
for key in VALUE_TO_STATE:
    STATE_TO_VALUE[VALUE_TO_STATE[key]] = key

STATES = [SPEED_OFF, SPEED_LOW, 'med', SPEED_HIGH]


# pylint: disable=unused-argument
def setup_platform(hass, config: ConfigType,
                   add_devices: Callable[[list], None], discovery_info=None):
    """Set up the ISY994 fan platform."""
    if isy.ISY is None or not isy.ISY.connected:
        _LOGGER.error("A connection has not been made to the ISY controller")
        return False

    devices = []

    for node in isy.filter_nodes(isy.NODES, states=STATES):
        devices.append(ISYFanDevice(node))

    for program in isy.PROGRAMS.get(DOMAIN, []):
        try:
            status = program[isy.KEY_STATUS]
            actions = program[isy.KEY_ACTIONS]
            assert actions.dtype == 'program', 'Not a program'
        except (KeyError, AssertionError):
            pass
        else:
            devices.append(ISYFanProgram(program.name, status, actions))

    add_devices(devices)


class ISYFanDevice(isy.ISYDevice, FanEntity):
    """Representation of an ISY994 fan device."""

    def __init__(self, node) -> None:
        """Initialize the ISY994 fan device."""
        isy.ISYDevice.__init__(self, node)

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return self.state

    @property
    def state(self) -> str:
        """Get the state of the ISY994 fan device."""
        return VALUE_TO_STATE.get(self.value, STATE_UNKNOWN)

    def set_speed(self, speed: str) -> None:
        """Send the set speed command to the ISY994 fan device."""
        if not self._node.on(val=STATE_TO_VALUE.get(speed, 0)):
            _LOGGER.debug("Unable to set fan speed")
        else:
            self.speed = self.state

    def turn_on(self, speed: str=None, **kwargs) -> None:
        """Send the turn on command to the ISY994 fan device."""
        self.set_speed(speed)

    def turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 fan device."""
        if not self._node.off():
            _LOGGER.debug("Unable to set fan speed")
        else:
            self.speed = self.state


class ISYFanProgram(ISYFanDevice):
    """Representation of an ISY994 fan program."""

    def __init__(self, name: str, node, actions) -> None:
        """Initialize the ISY994 fan program."""
        ISYFanDevice.__init__(self, node)
        self._name = name
        self._actions = actions
        self.speed = STATE_ON if self.is_on else STATE_OFF

    @property
    def state(self) -> str:
        """Get the state of the ISY994 fan program."""
        return STATE_ON if bool(self.value) else STATE_OFF

    def turn_off(self, **kwargs) -> None:
        """Send the turn on command to ISY994 fan program."""
        if not self._actions.runThen():
            _LOGGER.error("Unable to turn off the fan")
        else:
            self.speed = STATE_ON if self.is_on else STATE_OFF

    def turn_on(self, **kwargs) -> None:
        """Send the turn off command to ISY994 fan program."""
        if not self._actions.runElse():
            _LOGGER.error("Unable to turn on the fan")
        else:
            self.speed = STATE_ON if self.is_on else STATE_OFF
