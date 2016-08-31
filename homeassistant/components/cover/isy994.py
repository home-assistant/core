"""
Support for ISY994 covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.isy994/
"""
import logging

from homeassistant.components.isy994 import filter_nodes
from homeassistant.components.cover import CoverDevice, DOMAIN, ATTR_POSITION
from homeassistant.components.isy994 import (ISYDevice, NODES, PROGRAMS, ISY,
                                             KEY_ACTIONS, KEY_STATUS)
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
    """Setup the ISY platform."""

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
    """Representation of a ISY cover device."""

    def __init__(self, node):
        """Initialize the binary sensor."""
        ISYDevice.__init__(self, node)

    @property
    def current_cover_position(self):
        """Return the current cover position."""
        return sorted((0, self.value, 100))[1]

    @property
    def is_closed(self) -> bool:
        """Return true if device is locked."""
        return self.state == STATE_CLOSED

    @property
    def state(self) -> str:
        """Return the state of the device."""
        _LOGGER.error('STATE %s %s %s', self.name, self.value, VALUE_TO_STATE.get(self.value, STATE_OPEN))
        return VALUE_TO_STATE.get(self.value, STATE_OPEN)

    def open_cover(self, **kwargs):
        """Open the cover."""
        if not self._node.on(val=100):
            _LOGGER.error('Unable to open the cover')

    def close_cover(self, **kwargs):
        """Close cover."""
        if not self._node.off():
            _LOGGER.error('Unable to close the cover')


class ISYCoverProgram(ISYCoverDevice):
    """Representation of a ISY cover program."""

    def __init__(self, name, node, actions):
        """Initialize the cover."""
        ISYDevice.__init__(self, node)
        self._name = name
        self._actions = actions

    @property
    def is_closed(self) -> bool:
        """Return true if the device is locked."""
        return bool(self.value)

    @property
    def state(self):
        """Return cover state."""
        return STATE_CLOSED if self.is_closed else STATE_OPEN

    @property
    def unit_of_measurement(self) -> None:
        """No unit of measurement for lock programs."""
        return None

    def open_cover(self, **kwargs):
        """Open the cover."""
        if not self._actions.runThen():
            _LOGGER.error('Unable to open the cover')

    def close_cover(self, **kwargs):
        """Close the cover."""
        if not self._actions.runElse():
            _LOGGER.error('Unable to close the cover')
