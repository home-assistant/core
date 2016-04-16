"""
Support for MySensors switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.mysensors/
"""
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import ATTR_BATTERY_LEVEL, STATE_OFF, STATE_ON
from homeassistant.loader import get_component

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = []


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the mysensors platform for switches."""
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
            pres.S_DOOR: [set_req.V_ARMED],
            pres.S_MOTION: [set_req.V_ARMED],
            pres.S_SMOKE: [set_req.V_ARMED],
            pres.S_LIGHT: [set_req.V_LIGHT],
            pres.S_LOCK: [set_req.V_LOCK_STATUS],
        }
        if float(gateway.version) >= 1.5:
            map_sv_types.update({
                pres.S_BINARY: [set_req.V_STATUS, set_req.V_LIGHT],
                pres.S_SPRINKLER: [set_req.V_STATUS],
                pres.S_WATER_LEAK: [set_req.V_ARMED],
                pres.S_SOUND: [set_req.V_ARMED],
                pres.S_VIBRATION: [set_req.V_ARMED],
                pres.S_MOISTURE: [set_req.V_ARMED],
            })
            map_sv_types[pres.S_LIGHT].append(set_req.V_STATUS)

        devices = {}
        gateway.platform_callbacks.append(mysensors.pf_callback_factory(
            map_sv_types, devices, add_devices, MySensorsSwitch))


class MySensorsSwitch(SwitchDevice):
    """Representation of the value of a MySensors child node."""

    # pylint: disable=too-many-arguments,too-many-instance-attributes
    def __init__(
            self, gateway, node_id, child_id, name, value_type, child_type):
        """Setup class attributes on instantiation.

        Args:
        gateway (GatewayWrapper): Gateway object.
        node_id (str): Id of node.
        child_id (str): Id of child.
        name (str): Entity name.
        value_type (str): Value type of child. Value is entity state.
        child_type (str): Child type of child.

        Attributes:
        gateway (GatewayWrapper): Gateway object
        node_id (str): Id of node.
        child_id (str): Id of child.
        _name (str): Entity name.
        value_type (str): Value type of child. Value is entity state.
        battery_level (int): Node battery level.
        _values (dict): Child values. Non state values set as state attributes.
        mysensors (module): Mysensors main component module.
        """
        self.gateway = gateway
        self.node_id = node_id
        self.child_id = child_id
        self._name = name
        self.value_type = value_type
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
        """Return True if switch is on."""
        if self.value_type in self._values:
            return self._values[self.value_type] == STATE_ON
        return False

    def turn_on(self):
        """Turn the switch on."""
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, 1)
        if self.gateway.optimistic:
            # optimistically assume that switch has changed state
            self._values[self.value_type] = STATE_ON
            self.update_ha_state()

    def turn_off(self):
        """Turn the switch off."""
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, 0)
        if self.gateway.optimistic:
            # optimistically assume that switch has changed state
            self._values[self.value_type] = STATE_OFF
            self.update_ha_state()

    @property
    def available(self):
        """Return True if entity is available."""
        return self.value_type in self._values

    @property
    def assumed_state(self):
        """Return True if unable to access real state of entity."""
        return self.gateway.optimistic

    def update(self):
        """Update the controller with the latest value from a sensor."""
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        for value_type, value in child.values.items():
            _LOGGER.debug(
                "%s: value_type %s, value = %s", self._name, value_type, value)
            if value_type == self.gateway.const.SetReq.V_ARMED or \
               value_type == self.gateway.const.SetReq.V_LIGHT or \
               value_type == self.gateway.const.SetReq.V_LOCK_STATUS:
                self._values[value_type] = (
                    STATE_ON if int(value) == 1 else STATE_OFF)
            else:
                self._values[value_type] = value
        self.battery_level = node.battery_level
