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
DEPENDENCIES = ['mysensors']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Setup the mysensors platform for sensors. """

    # Define the V_TYPES that the platform should handle as states.
    v_types = []
    for _, member in mysensors.CONST.SetReq.__members__.items():
        if (member.value != mysensors.CONST.SetReq.V_ARMED and
                member.value != mysensors.CONST.SetReq.V_STATUS and
                member.value != mysensors.CONST.SetReq.V_LIGHT and
                member.value != mysensors.CONST.SetReq.V_LOCK_STATUS):
            v_types.append(member)

    @mysensors.mysensors_update
    def _sensor_update(gateway, port, devices, nid):
        """Internal callback for sensor updates."""
        return (v_types, MySensorsSensor, add_devices)

    def sensor_update(event):
        """ Callback for sensor updates from the MySensors component. """
        _LOGGER.info(
            'update %s: node %s', event.data[mysensors.ATTR_UPDATE_TYPE],
            event.data[mysensors.ATTR_NODE_ID])
        _sensor_update(mysensors.GATEWAYS[event.data[mysensors.ATTR_PORT]],
                       event.data[mysensors.ATTR_PORT],
                       event.data[mysensors.ATTR_DEVICES],
                       event.data[mysensors.ATTR_NODE_ID])

    hass.bus.listen(mysensors.EVENT_MYSENSORS_NODE_UPDATE, sensor_update)


class MySensorsSensor(Entity):

    """ Represents the value of a MySensors child node. """
    # pylint: disable=too-many-arguments, too-many-instance-attributes

    def __init__(self, port, node_id, child_id, name, value_type):
        self.port = port
        self._name = name
        self.node_id = node_id
        self.child_id = child_id
        self.battery_level = 0
        self.value_type = value_type
        self._values = {}

    def as_dict(self):
        """ Returns a dict representation of this Entity. """
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
        """ MySensor gateway pushes its state to HA.  """
        return False

    @property
    def name(self):
        """ The name of this sensor. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        if not self._values:
            return ''
        return self._values[self.value_type]

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity. """
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
        """ Returns device specific state attributes. """
        device_attr = dict(self._values)
        device_attr.pop(self.value_type, None)
        return device_attr

    @property
    def state_attributes(self):
        """ Returns the state attributes. """

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
        """ Update the controller with the latest values from a sensor. """
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
