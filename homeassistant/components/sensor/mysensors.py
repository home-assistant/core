"""
homeassistant.components.sensor.mysensors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for MySensors sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mysensors/
"""
import logging

from homeassistant.helpers.entity import Entity

from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    TEMP_CELCIUS,
    STATE_ON, STATE_OFF)

import homeassistant.components.mysensors as mysensors

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = []


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the mysensors platform for sensors."""
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
            gateway.const.Presentation.S_TEMP,
            gateway.const.Presentation.S_HUM,
            gateway.const.Presentation.S_BARO,
            gateway.const.Presentation.S_WIND,
            gateway.const.Presentation.S_RAIN,
            gateway.const.Presentation.S_UV,
            gateway.const.Presentation.S_WEIGHT,
            gateway.const.Presentation.S_POWER,
            gateway.const.Presentation.S_DISTANCE,
            gateway.const.Presentation.S_LIGHT_LEVEL,
            gateway.const.Presentation.S_IR,
            gateway.const.Presentation.S_WATER,
            gateway.const.Presentation.S_AIR_QUALITY,
            gateway.const.Presentation.S_CUSTOM,
            gateway.const.Presentation.S_DUST,
            gateway.const.Presentation.S_SCENE_CONTROLLER,
        ]
        not_v_types = [
            gateway.const.SetReq.V_ARMED,
            gateway.const.SetReq.V_LIGHT,
            gateway.const.SetReq.V_LOCK_STATUS,
            gateway.const.SetReq.V_UNIT_PREFIX,
        ]
        if float(gateway.version) >= 1.5:
            s_types.extend([
                gateway.const.Presentation.S_COLOR_SENSOR,
                gateway.const.Presentation.S_MULTIMETER,
                gateway.const.Presentation.S_SPRINKLER,
                gateway.const.Presentation.S_WATER_LEAK,
                gateway.const.Presentation.S_SOUND,
                gateway.const.Presentation.S_VIBRATION,
                gateway.const.Presentation.S_MOISTURE,
            ])
            not_v_types.extend([gateway.const.SetReq.V_STATUS, ])
        v_types = [member for member in gateway.const.SetReq
                   if member.value not in not_v_types]

        devices = {}
        gateway.platform_callbacks.append(mysensors.pf_callback_factory(
            s_types, v_types, devices, add_devices, MySensorsSensor))


class MySensorsSensor(Entity):
    """Represent the value of a MySensors child node."""

    # pylint: disable=too-many-arguments

    def __init__(self, gateway, node_id, child_id, name, value_type):
        """Setup class attributes on instantiation.

        Args:
        gateway (GatewayWrapper): Gateway object.
        node_id (str): Id of node.
        child_id (str): Id of child.
        name (str): Entity name.
        value_type (str): Value type of child. Value is entity state.

        Attributes:
        gateway (GatewayWrapper): Gateway object.
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
    def state(self):
        """Return the state of the device."""
        if not self._values:
            return ''
        return self._values[self.value_type]

    @property
    def unit_of_measurement(self):
        """Unit of measurement of this entity."""
        # HA will convert to degrees F if needed
        unit_map = {
            self.gateway.const.SetReq.V_TEMP: TEMP_CELCIUS,
            self.gateway.const.SetReq.V_HUM: '%',
            self.gateway.const.SetReq.V_DIMMER: '%',
            self.gateway.const.SetReq.V_LIGHT_LEVEL: '%',
            self.gateway.const.SetReq.V_WEIGHT: 'kg',
            self.gateway.const.SetReq.V_DISTANCE: 'm',
            self.gateway.const.SetReq.V_IMPEDANCE: 'ohm',
            self.gateway.const.SetReq.V_WATT: 'W',
            self.gateway.const.SetReq.V_KWH: 'kWh',
            self.gateway.const.SetReq.V_FLOW: 'm',
            self.gateway.const.SetReq.V_VOLUME: 'm3',
            self.gateway.const.SetReq.V_VOLTAGE: 'V',
            self.gateway.const.SetReq.V_CURRENT: 'A',
        }
        unit_map_v15 = {
            self.gateway.const.SetReq.V_PERCENTAGE: '%',
        }
        if float(self.gateway.version) >= 1.5:
            if self.gateway.const.SetReq.V_UNIT_PREFIX in self._values:
                return self._values[
                    self.gateway.const.SetReq.V_UNIT_PREFIX]
            unit_map.update(unit_map_v15)
        return unit_map.get(self.value_type)

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        device_attr = {}
        for value_type, value in self._values.items():
            if value_type != self.value_type:
                device_attr[self.gateway.const.SetReq(value_type).name] = value
        return device_attr

    @property
    def state_attributes(self):
        """Return the state attributes."""
        data = {
            mysensors.ATTR_PORT: self.gateway.port,
            mysensors.ATTR_NODE_ID: self.node_id,
            mysensors.ATTR_CHILD_ID: self.child_id,
            ATTR_BATTERY_LEVEL: self.battery_level,
        }

        device_attr = self.device_state_attributes

        if device_attr is not None:
            data.update(device_attr)

        return data

    def update(self):
        """Update the controller with the latest values from a sensor."""
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        for value_type, value in child.values.items():
            _LOGGER.info(
                "%s: value_type %s, value = %s", self._name, value_type, value)
            if value_type == self.gateway.const.SetReq.V_TRIPPED:
                self._values[value_type] = STATE_ON if int(
                    value) == 1 else STATE_OFF
            else:
                self._values[value_type] = value

        self.battery_level = node.battery_level
