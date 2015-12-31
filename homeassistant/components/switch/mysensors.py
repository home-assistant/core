"""
homeassistant.components.switch.mysensors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for MySensors switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mysensors.html
"""
import logging
from collections import defaultdict

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


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the mysensors platform for switches."""
    # Only act if loaded via mysensors by discovery event.
    # Otherwise gateway is not setup.
    if discovery_info is None:
        return

    for gateway in mysensors.GATEWAYS.values():
        # Define the S_TYPES and V_TYPES that the platform should handle as
        # states.
        s_types = [
            gateway.const.Presentation.S_DOOR,
            gateway.const.Presentation.S_MOTION,
            gateway.const.Presentation.S_SMOKE,
            gateway.const.Presentation.S_LIGHT,
            gateway.const.Presentation.S_BINARY,
            gateway.const.Presentation.S_LOCK,
        ]
        v_types = [
            gateway.const.SetReq.V_ARMED,
            gateway.const.SetReq.V_LIGHT,
            gateway.const.SetReq.V_LOCK_STATUS,
        ]
        if float(gateway.version) >= 1.5:
            s_types.extend([
                gateway.const.Presentation.S_SPRINKLER,
                gateway.const.Presentation.S_WATER_LEAK,
                gateway.const.Presentation.S_SOUND,
                gateway.const.Presentation.S_VIBRATION,
                gateway.const.Presentation.S_MOISTURE,
            ])
            v_types.extend([gateway.const.SetReq.V_STATUS, ])

        devices = defaultdict(list)
        gateway.platform_callbacks.append(mysensors.pf_callback_factory(
            s_types, v_types, devices, add_devices, MySensorsSwitch))


class MySensorsSwitch(SwitchDevice):
    """Represent the value of a MySensors child node."""

    # pylint: disable=too-many-arguments

    def __init__(self, gateway, node_id, child_id, name, value_type):
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
        self.gateway = gateway
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
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, 1)
        self._values[self.value_type] = STATE_ON
        self.update_ha_state()

    def turn_off(self):
        """Turn the switch off."""
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, 0)
        self._values[self.value_type] = STATE_OFF
        self.update_ha_state()

    def update(self):
        """Update the controller with the latest value from a sensor."""
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        for value_type, value in child.values.items():
            _LOGGER.info(
                "%s: value_type %s, value = %s", self._name, value_type, value)
            if value_type == self.gateway.const.SetReq.V_ARMED or \
               value_type == self.gateway.const.SetReq.V_STATUS or \
               value_type == self.gateway.const.SetReq.V_LIGHT or \
               value_type == self.gateway.const.SetReq.V_LOCK_STATUS:
                self._values[value_type] = (
                    STATE_ON if int(value) == 1 else STATE_OFF)
            else:
                self._values[value_type] = value
        self.battery_level = node.battery_level
