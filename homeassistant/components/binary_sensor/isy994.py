"""
Support for ISY994 binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.isy994/
"""
import logging
from typing import Callable  # noqa

from homeassistant.components.binary_sensor import BinarySensorDevice, DOMAIN
import homeassistant.components.isy994 as isy
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.helpers.typing import ConfigType


_LOGGER = logging.getLogger(__name__)

VALUE_TO_STATE = {
    False: STATE_OFF,
    True: STATE_ON,
}

UOM = ['2', '78']
STATES = [STATE_OFF, STATE_ON, 'true', 'false']


# pylint: disable=unused-argument
def setup_platform(hass, config: ConfigType,
                   add_devices: Callable[[list], None], discovery_info=None):
    """Setup the ISY994 binary sensor platform."""
    if isy.ISY is None or not isy.ISY.connected:
        _LOGGER.error('A connection has not been made to the ISY controller.')
        return False

    devices = []

    for node in isy.filter_nodes(isy.SENSOR_NODES, units=UOM,
                                 states=STATES):
        devices.append(ISYBinarySensorDevice(node))

    for program in isy.PROGRAMS.get(DOMAIN, []):
        try:
            status = program[isy.KEY_STATUS]
        except (KeyError, AssertionError):
            pass
        else:
            devices.append(ISYBinarySensorProgram(program.name, status))

    add_devices(devices)


class ISYBinarySensorDevice(isy.ISYDevice, BinarySensorDevice):
    """Representation of an ISY994 binary sensor device."""

    def __init__(self, node) -> None:
        """Initialize the ISY994 binary sensor device."""
        isy.ISYDevice.__init__(self, node)

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 binary sensor device is on."""
        return bool(self.value)


class ISYBinarySensorProgram(ISYBinarySensorDevice):
    """Representation of an ISY994 binary sensor program."""

    def __init__(self, name, node) -> None:
        """Initialize the ISY994 binary sensor program."""
        ISYBinarySensorDevice.__init__(self, node)
        self._name = name
