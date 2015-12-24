"""
homeassistant.components.switch.mysensors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for MySensors switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mysensors.html
"""
import logging

from homeassistant.components.switch import SwitchDevice

from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    STATE_ON, STATE_OFF)

import homeassistant.components.mysensors as mysensors

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = []

ADD_DEVICES = None
S_TYPES = None
V_TYPES = None


@mysensors.mysensors_update
def sensor_update(gateway, port, devices, nid):
    """Internal callback for sensor updates."""
    return (S_TYPES, V_TYPES, MySensorsSwitch, ADD_DEVICES)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the mysensors platform for switches."""
    # Define the S_TYPES and V_TYPES that the platform should handle as states.
    global ADD_DEVICES
    ADD_DEVICES = add_devices
    global S_TYPES
    S_TYPES = [
        mysensors.CONST.Presentation.S_DOOR,
        mysensors.CONST.Presentation.S_MOTION,
        mysensors.CONST.Presentation.S_SMOKE,
        mysensors.CONST.Presentation.S_LIGHT,
        mysensors.CONST.Presentation.S_BINARY,
        mysensors.CONST.Presentation.S_LOCK,
    ]
    global V_TYPES
    V_TYPES = [
        mysensors.CONST.SetReq.V_ARMED,
        mysensors.CONST.SetReq.V_LIGHT,
        mysensors.CONST.SetReq.V_LOCK_STATUS,
    ]
    if float(mysensors.VERSION) >= 1.5:
        S_TYPES.extend([
            mysensors.CONST.Presentation.S_SPRINKLER,
            mysensors.CONST.Presentation.S_WATER_LEAK,
            mysensors.CONST.Presentation.S_SOUND,
            mysensors.CONST.Presentation.S_VIBRATION,
            mysensors.CONST.Presentation.S_MOISTURE,
        ])
        V_TYPES.extend([mysensors.CONST.SetReq.V_STATUS, ])


class MySensorsSwitch(SwitchDevice):
    """Represent the value of a MySensors child node."""

    # pylint: disable=too-many-arguments, too-many-instance-attributes

    def __init__(self, port, node_id, child_id, name, value_type):
        """Setup class attributes on instantiation.

        Args:
        port (str): Gateway port.
        node_id (str): Id of node.
        child_id (str): Id of child.
        name (str): Entity name.
        value_type (str): Value type of child. Value is entity state.

        Attributes:
        port (str): Gateway port.
        node_id (str): Id of node.
        child_id (str): Id of child.
        _name (str): Entity name.
        value_type (str): Value type of child. Value is entity state.
        battery_level (int): Node battery level.
        _values (dict): Child values. Non state values set as state attributes.
        """
        self.port = port
        self.node_id = node_id
        self.child_id = child_id
        self._name = name
        self.value_type = value_type
        self.battery_level = 0
        self._values = {}

    @property
    def should_poll(self):
        """MySensor gateway pushes its state to HA."""
        return False

    @property
    def name(self):
        """The name of this entity."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        device_attr = dict(self._values)
        device_attr.pop(self.value_type, None)
        return device_attr

    @property
    def state_attributes(self):
        """Return the state attributes."""
        data = {
            mysensors.ATTR_NODE_ID: self.node_id,
            mysensors.ATTR_CHILD_ID: self.child_id,
            ATTR_BATTERY_LEVEL: self.battery_level,
        }

        device_attr = self.device_state_attributes

        if device_attr is not None:
            data.update(device_attr)

        return data

    @property
    def is_on(self):
        """Return True if switch is on."""
        if self.value_type in self._values:
            return self._values[self.value_type] == STATE_ON
        return False

    def turn_on(self):
        """Turn the switch on."""
        mysensors.GATEWAYS[self.port].set_child_value(
            self.node_id, self.child_id, self.value_type, 1)
        self._values[self.value_type] = STATE_ON
        self.update_ha_state()

    def turn_off(self):
        """Turn the switch off."""
        mysensors.GATEWAYS[self.port].set_child_value(
            self.node_id, self.child_id, self.value_type, 0)
        self._values[self.value_type] = STATE_OFF
        self.update_ha_state()

    def update_sensor(self, values, battery_level):
        """Update the controller with the latest value from a sensor."""
        for value_type, value in values.items():
            _LOGGER.info(
                "%s: value_type %s, value = %s", self._name, value_type, value)
            if value_type == mysensors.CONST.SetReq.V_ARMED or \
               value_type == mysensors.CONST.SetReq.V_STATUS or \
               value_type == mysensors.CONST.SetReq.V_LIGHT or \
               value_type == mysensors.CONST.SetReq.V_LOCK_STATUS:
                self._values[value_type] = (
                    STATE_ON if int(value) == 1 else STATE_OFF)
            else:
                self._values[value_type] = value
        self.battery_level = battery_level
        self.update_ha_state()
