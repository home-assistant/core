"""
Support for ISY994 fans.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/fan.isy994/
"""
import logging

from homeassistant.components.isy994 import filter_nodes
from homeassistant.components.fan import (FanEntity, DOMAIN, ATTR_SPEED,
                                          SPEED_OFF, SPEED_LOW, SPEED_MED,
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
    """Setup the ISY platform."""

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
    """Representation of a ISY fan device."""

    def __init__(self, node):
        """Initialize the binary sensor."""
        ISYDevice.__init__(self, node)
        self.speed = self.state

    @property
    def state(self) -> str:
        """Return the state of the device."""
        return VALUE_TO_STATE.get(self.value, STATE_UNKNOWN)

    def set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        if not self._node.on(val=STATE_TO_VALUE.get(speed, 0)):
            _LOGGER.debug('Unable to set fan speed')
        else:
            self.speed = self.state

    def turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the fan."""
        self.set_speed(speed)

    def turn_off(self, **kwargs) -> None:
        """Turn off the fan."""
        if not self._node.off():
            _LOGGER.debug('Unable to set fan speed')
        else:
            self.speed = self.state


class ISYFanProgram(ISYFanDevice):
    """Representation of a ISY cover program."""

    def __init__(self, name, node, actions):
        """Initialize the cover."""
        ISYDevice.__init__(self, node)
        self._name = name
        self._actions = actions
        self.speed = STATE_ON if self.is_on() else STATE_OFF

    @property
    def is_on(self) -> bool:
        """Return true if the device is locked."""
        return bool(self.value)

    @property
    def state(self):
        """Return state of the fan."""
        return STATE_ON if self.is_on else STATE_OFF

    def turn_off(self, **kwargs):
        """Turn fan on."""
        if not self._actions.runThen():
            _LOGGER.error('Unable to open the cover')
        else:
            self.speed = STATE_ON if self.is_on() else STATE_OFF

    def turn_on(self, **kwargs):
        """Turn fan off."""
        if not self._actions.runElse():
            _LOGGER.error('Unable to close the cover')
        else:
            self.speed = STATE_ON if self.is_on() else STATE_OFF
