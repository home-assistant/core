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
    """
    Setup the ISY994 binary sensor platform.

    :param hass: HomeAssistant
    :param config: The platform configuration.
    :param add_devices: The add device callback method.
    :param discovery_info: The discovery information.
    :return: Whether the platform was setup properly.
    """
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
    """
    Representation of an ISY994 binary sensor device.
    """

    def __init__(self, node):
        """
        Initialize the ISY994 binary sensor device.

        :param node: The ISY994 node.
        """
        ISYDevice.__init__(self, node)

    @property
    def is_on(self) -> bool:
        """
        Get whether the ISY994 binary sensor device is on.

        :return: Whether the ISY994 binary sensor device is in the 'on' state.
        """
        return self.state == STATE_ON

    @property
    def state(self) -> str:
        """
        Get the state of the ISY994 binary sensor device.

        :return: The state of the ISY994 binary sensor device.
        """
        return VALUE_TO_STATE.get(self.value, STATE_UNKNOWN)


class ISYBinarySensorProgram(ISYBinarySensorDevice):
    """
    Representation of an ISY994 binary sensor program.
    """

    def __init__(self, name, node):
        """
        Initialize the ISY994 binary sensor program.

        :param name: The name of the ISY994 binary sensor.
        :param node: The ISY994 program to get the sensor status.
        """
        ISYDevice.__init__(self, node)
        self._name = name

    @property
    def state(self) -> bool:
        """
        Get state of the ISY994 binary sensor program.

        :return: The state of the ISY994 binary sensor program.
        """
        return STATE_ON if bool(self.value) else STATE_OFF
