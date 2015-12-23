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
    TEMP_CELCIUS, TEMP_FAHRENHEIT,
    STATE_ON, STATE_OFF)

import homeassistant.components.mysensors as mysensors

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = []


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the mysensors platform for sensors."""
    # Define the S_TYPES and V_TYPES that the platform should handle as states.
    s_types = [
        mysensors.CONST.Presentation.S_TEMP,
        mysensors.CONST.Presentation.S_HUM,
        mysensors.CONST.Presentation.S_BARO,
        mysensors.CONST.Presentation.S_WIND,
        mysensors.CONST.Presentation.S_RAIN,
        mysensors.CONST.Presentation.S_UV,
        mysensors.CONST.Presentation.S_WEIGHT,
        mysensors.CONST.Presentation.S_POWER,
        mysensors.CONST.Presentation.S_DISTANCE,
        mysensors.CONST.Presentation.S_LIGHT_LEVEL,
        mysensors.CONST.Presentation.S_IR,
        mysensors.CONST.Presentation.S_WATER,
        mysensors.CONST.Presentation.S_AIR_QUALITY,
        mysensors.CONST.Presentation.S_CUSTOM,
        mysensors.CONST.Presentation.S_DUST,
        mysensors.CONST.Presentation.S_SCENE_CONTROLLER,
    ]
    not_v_types = [
        mysensors.CONST.SetReq.V_ARMED,
        mysensors.CONST.SetReq.V_LIGHT,
        mysensors.CONST.SetReq.V_LOCK_STATUS,
    ]
    if float(mysensors.VERSION) >= 1.5:
        s_types.extend([
            mysensors.CONST.Presentation.S_COLOR_SENSOR,
            mysensors.CONST.Presentation.S_MULTIMETER,
        ])
        not_v_types.extend([mysensors.CONST.SetReq.V_STATUS, ])
    v_types = [member for member in mysensors.CONST.SetReq
               if member.value not in not_v_types]

    @mysensors.mysensors_update
    def _sensor_update(gateway, port, devices, nid):
        """Internal callback for sensor updates."""
        return (s_types, v_types, MySensorsSensor, add_devices)

    @mysensors.event_update
    def event_update(event):
        """Callback for event updates from the MySensors component."""
        return _sensor_update

    hass.bus.listen(mysensors.EVENT_MYSENSORS_NODE_UPDATE, event_update)


class MySensorsSensor(Entity):
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

    def as_dict(self):
        """Return a dict representation of this entity."""
        return {
            'port': self.port,
            'name': self._name,
            'node_id': self.node_id,
            'child_id': self.child_id,
            'battery_level': self.battery_level,
            'value_type': self.value_type,
            'values': self._values,
        }

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
        # pylint:disable=too-many-return-statements
        if self.value_type == mysensors.CONST.SetReq.V_TEMP:
            return TEMP_CELCIUS if mysensors.IS_METRIC else TEMP_FAHRENHEIT
        elif self.value_type == mysensors.CONST.SetReq.V_HUM or \
                self.value_type == mysensors.CONST.SetReq.V_DIMMER or \
                self.value_type == mysensors.CONST.SetReq.V_PERCENTAGE or \
                self.value_type == mysensors.CONST.SetReq.V_LIGHT_LEVEL:
            return '%'
        elif self.value_type == mysensors.CONST.SetReq.V_WATT:
            return 'W'
        elif self.value_type == mysensors.CONST.SetReq.V_KWH:
            return 'kWh'
        elif self.value_type == mysensors.CONST.SetReq.V_VOLTAGE:
            return 'V'
        elif self.value_type == mysensors.CONST.SetReq.V_CURRENT:
            return 'A'
        elif self.value_type == mysensors.CONST.SetReq.V_IMPEDANCE:
            return 'ohm'
        elif mysensors.CONST.SetReq.V_UNIT_PREFIX in self._values:
            return self._values[mysensors.CONST.SetReq.V_UNIT_PREFIX]
        return None

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

    def update_sensor(self, values, battery_level):
        """Update the controller with the latest values from a sensor."""
        for value_type, value in values.items():
            _LOGGER.info(
                "%s: value_type %s, value = %s", self._name, value_type, value)
            if value_type == mysensors.CONST.SetReq.V_TRIPPED:
                self._values[value_type] = STATE_ON if int(
                    value) == 1 else STATE_OFF
            else:
                self._values[value_type] = value

        self.battery_level = battery_level
        self.update_ha_state()
