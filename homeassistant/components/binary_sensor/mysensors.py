"""
Support for MySensors binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.mysensors/
"""
import logging

from homeassistant.const import (
    ATTR_BATTERY_LEVEL, STATE_OFF, STATE_ON)
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, SENSOR_CLASSES)
from homeassistant.loader import get_component

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = []


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the mysensors platform for sensors."""
    # Only act if loaded via mysensors by discovery event.
    # Otherwise gateway is not setup.
    if discovery_info is None:
        return

    mysensors = get_component('mysensors')

    for gateway in mysensors.GATEWAYS.values():
        # Define the S_TYPES and V_TYPES that the platform should handle as
        # states. Map them in a dict of lists.
        pres = gateway.const.Presentation
        set_req = gateway.const.SetReq
        map_sv_types = {
            pres.S_DOOR: [set_req.V_TRIPPED],
            pres.S_MOTION: [set_req.V_TRIPPED],
            pres.S_SMOKE: [set_req.V_TRIPPED],
        }
        if float(gateway.version) >= 1.5:
            map_sv_types.update({
                pres.S_SPRINKLER: [set_req.V_TRIPPED],
                pres.S_WATER_LEAK: [set_req.V_TRIPPED],
                pres.S_SOUND: [set_req.V_TRIPPED],
                pres.S_VIBRATION: [set_req.V_TRIPPED],
                pres.S_MOISTURE: [set_req.V_TRIPPED],
            })

        devices = {}
        gateway.platform_callbacks.append(mysensors.pf_callback_factory(
            map_sv_types, devices, add_devices, MySensorsBinarySensor))


class MySensorsBinarySensor(BinarySensorDevice):
    """Represent the value of a MySensors child node."""

    # pylint: disable=too-many-arguments,too-many-instance-attributes

    def __init__(
            self, gateway, node_id, child_id, name, value_type, child_type):
        """
        Setup class attributes on instantiation.

        Args:
        gateway (GatewayWrapper): Gateway object.
        node_id (str): Id of node.
        child_id (str): Id of child.
        name (str): Entity name.
        value_type (str): Value type of child. Value is entity state.
        child_type (str): Child type of child.

        Attributes:
        gateway (GatewayWrapper): Gateway object.
        node_id (str): Id of node.
        child_id (str): Id of child.
        _name (str): Entity name.
        value_type (str): Value type of child. Value is entity state.
        child_type (str): Child type of child.
        battery_level (int): Node battery level.
        _values (dict): Child values. Non state values set as state attributes.
        mysensors (module): Mysensors main component module.
        """
        self.gateway = gateway
        self.node_id = node_id
        self.child_id = child_id
        self._name = name
        self.value_type = value_type
        self.child_type = child_type
        self.battery_level = 0
        self._values = {}
        self.mysensors = get_component('mysensors')

    @property
    def should_poll(self):
        """Mysensor gateway pushes its state to HA."""
        return False

    @property
    def name(self):
        """The name of this entity."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attr = {
            self.mysensors.ATTR_PORT: self.gateway.port,
            self.mysensors.ATTR_NODE_ID: self.node_id,
            self.mysensors.ATTR_CHILD_ID: self.child_id,
            ATTR_BATTERY_LEVEL: self.battery_level,
        }

        set_req = self.gateway.const.SetReq

        for value_type, value in self._values.items():
            if value_type != self.value_type:
                try:
                    attr[set_req(value_type).name] = value
                except ValueError:
                    _LOGGER.error('value_type %s is not valid for mysensors '
                                  'version %s', value_type,
                                  self.gateway.version)
        return attr

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        if self.value_type in self._values:
            return self._values[self.value_type] == STATE_ON
        return False

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        pres = self.gateway.const.Presentation
        class_map = {
            pres.S_DOOR: 'opening',
            pres.S_MOTION: 'motion',
            pres.S_SMOKE: 'smoke',
        }
        if float(self.gateway.version) >= 1.5:
            class_map.update({
                pres.S_SPRINKLER: 'sprinkler',
                pres.S_WATER_LEAK: 'leak',
                pres.S_SOUND: 'sound',
                pres.S_VIBRATION: 'vibration',
                pres.S_MOISTURE: 'moisture',
            })
        if class_map.get(self.child_type) in SENSOR_CLASSES:
            return class_map.get(self.child_type)

    @property
    def available(self):
        """Return True if entity is available."""
        return self.value_type in self._values

    def update(self):
        """Update the controller with the latest values from a sensor."""
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        for value_type, value in child.values.items():
            _LOGGER.debug(
                "%s: value_type %s, value = %s", self._name, value_type, value)
            if value_type == self.gateway.const.SetReq.V_TRIPPED:
                self._values[value_type] = STATE_ON if int(
                    value) == 1 else STATE_OFF
            else:
                self._values[value_type] = value

        self.battery_level = node.battery_level
