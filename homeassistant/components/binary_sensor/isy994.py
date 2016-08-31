"""
Support for ISY994 binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.isy994/
"""
import logging

from homeassistant.components.isy994 import filter_nodes
from homeassistant.components.binary_sensor import BinarySensorDevice, DOMAIN
from homeassistant.components.isy994 import (ISYDevice, SENSOR_NODES, PROGRAMS, ISY,
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

    for node in filter_nodes(SENSOR_NODES, units=UOM,
                             states=STATES):
        devices.append(ISYBinarySensorDevice(node))

    for program in PROGRAMS.get(DOMAIN, []):
        try:
            status = program[KEY_STATUS]
        except (KeyError, AssertionError):
            pass
        else:
            devices.append(ISYBinarySensorProgram(program.name, status))

    add_devices(devices)


class ISYBinarySensorDevice(ISYDevice, BinarySensorDevice):
    """Representation of a ISY binary sensor."""

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


class ISYBinarySensorProgram(ISYBinarySensorDevice):
    """Representation of a ISY lock program."""

    def __init__(self, name, node):
        """Initialize the lock."""
        ISYDevice.__init__(self, node)
        self._name = name

    @property
    def is_on(self) -> bool:
        """Return true if the device is locked."""
        return bool(self.value)
