"""
Support for MySensors sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mysensors/
"""
import logging

from homeassistant.const import (
    ATTR_BATTERY_LEVEL, STATE_OFF, STATE_ON, TEMP_CELCIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.entity import Entity
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
            pres.S_TEMP: [set_req.V_TEMP],
            pres.S_HUM: [set_req.V_HUM],
            pres.S_BARO: [set_req.V_PRESSURE, set_req.V_FORECAST],
            pres.S_WIND: [set_req.V_WIND, set_req.V_GUST],
            pres.S_RAIN: [set_req.V_RAIN, set_req.V_RAINRATE],
            pres.S_UV: [set_req.V_UV],
            pres.S_WEIGHT: [set_req.V_WEIGHT, set_req.V_IMPEDANCE],
            pres.S_POWER: [set_req.V_WATT, set_req.V_KWH],
            pres.S_DISTANCE: [set_req.V_DISTANCE],
            pres.S_LIGHT_LEVEL: [set_req.V_LIGHT_LEVEL],
            pres.S_IR: [set_req.V_IR_SEND, set_req.V_IR_RECEIVE],
            pres.S_WATER: [set_req.V_FLOW, set_req.V_VOLUME],
            pres.S_CUSTOM: [set_req.V_VAR1,
                            set_req.V_VAR2,
                            set_req.V_VAR3,
                            set_req.V_VAR4,
                            set_req.V_VAR5],
            pres.S_SCENE_CONTROLLER: [set_req.V_SCENE_ON,
                                      set_req.V_SCENE_OFF],
        }
        if float(gateway.version) < 1.5:
            map_sv_types.update({
                pres.S_AIR_QUALITY: [set_req.V_DUST_LEVEL],
                pres.S_DUST: [set_req.V_DUST_LEVEL],
            })
        if float(gateway.version) >= 1.5:
            map_sv_types.update({
                pres.S_COLOR_SENSOR: [set_req.V_RGB],
                pres.S_MULTIMETER: [set_req.V_VOLTAGE,
                                    set_req.V_CURRENT,
                                    set_req.V_IMPEDANCE],
                pres.S_SOUND: [set_req.V_LEVEL],
                pres.S_VIBRATION: [set_req.V_LEVEL],
                pres.S_MOISTURE: [set_req.V_LEVEL],
                pres.S_AIR_QUALITY: [set_req.V_LEVEL],
                pres.S_DUST: [set_req.V_LEVEL],
            })
            map_sv_types[pres.S_LIGHT_LEVEL].append(set_req.V_LEVEL)

        devices = {}
        gateway.platform_callbacks.append(mysensors.pf_callback_factory(
            map_sv_types, devices, add_devices, MySensorsSensor))


class MySensorsSensor(Entity):
    """Represent the value of a MySensors child node."""

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
        gateway (GatewayWrapper): Gateway object.
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
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of this entity."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if not self._values:
            return ''
        return self._values[self.value_type]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        set_req = self.gateway.const.SetReq
        unit_map = {
            set_req.V_TEMP: (TEMP_CELCIUS
                             if self.gateway.metric else TEMP_FAHRENHEIT),
            set_req.V_HUM: '%',
            set_req.V_DIMMER: '%',
            set_req.V_LIGHT_LEVEL: '%',
            set_req.V_WEIGHT: 'kg',
            set_req.V_DISTANCE: 'm',
            set_req.V_IMPEDANCE: 'ohm',
            set_req.V_WATT: 'W',
            set_req.V_KWH: 'kWh',
            set_req.V_FLOW: 'm',
            set_req.V_VOLUME: 'm3',
            set_req.V_VOLTAGE: 'V',
            set_req.V_CURRENT: 'A',
        }
        if float(self.gateway.version) >= 1.5:
            if set_req.V_UNIT_PREFIX in self._values:
                return self._values[
                    set_req.V_UNIT_PREFIX]
            unit_map.update({set_req.V_PERCENTAGE: '%'})
        return unit_map.get(self.value_type)

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
