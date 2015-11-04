"""
homeassistant.components.sensor.mysensors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for MySensors switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mysensors.html
"""
import logging

from homeassistant.components.switch import SwitchDevice

from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    TEMP_CELCIUS, TEMP_FAHRENHEIT,
    STATE_ON, STATE_OFF)

import homeassistant.components.mysensors as mysensors

ATTR_NODE_ID = "node_id"
ATTR_CHILD_ID = "child_id"

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['mysensors']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Setup the mysensors platform for switches. """

    v_types = []
    for _, member in mysensors.CONST.SetReq.__members__.items():
        if (member.value == mysensors.CONST.SetReq.V_STATUS or
                member.value == mysensors.CONST.SetReq.V_LIGHT or
                member.value == mysensors.CONST.SetReq.V_LOCK_STATUS):
            v_types.append(member)

    @mysensors.mysensors_update
    def _sensor_update(gateway, devices, nid):
        """Internal callback for sensor updates."""
        _LOGGER.info("sensor update = %s", devices)
        return {'types_to_handle': v_types,
                'platform_class': MySensorsSwitch,
                'add_devices': add_devices}

    def sensor_update(event):
        """ Callback for sensor updates from the MySensors component. """
        _LOGGER.info(
            'update %s: node %s', event.data[mysensors.UPDATE_TYPE],
            event.data[mysensors.NODE_ID])
        _sensor_update(mysensors.GATEWAY, mysensors.DEVICES,
                       event.data[mysensors.NODE_ID])

    hass.bus.listen(mysensors.EVENT_MYSENSORS_NODE_UPDATE, sensor_update)


class MySensorsSwitch(SwitchDevice):

    """ Represents the value of a MySensors child node. """
    # pylint: disable=too-many-arguments, too-many-instance-attributes

    def __init__(self, gateway, node_id, child_id, name, value_type):
        self.gateway = gateway
        self._name = name
        self.node_id = node_id
        self.child_id = child_id
        self.battery_level = 0
        self.value_type = value_type
        self.metric = mysensors.IS_METRIC
        self._value = STATE_OFF
        self.const = mysensors.CONST

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
        return self._value

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity. """
        if self.value_type == self.const.SetReq.V_TEMP:
            return TEMP_CELCIUS if self.metric else TEMP_FAHRENHEIT
        elif self.value_type == self.const.SetReq.V_HUM or \
                self.value_type == self.const.SetReq.V_DIMMER or \
                self.value_type == self.const.SetReq.V_LIGHT_LEVEL:
            return '%'
        return None

    @property
    def state_attributes(self):
        """ Returns the state attributes. """
        return {
            ATTR_NODE_ID: self.node_id,
            ATTR_CHILD_ID: self.child_id,
            ATTR_BATTERY_LEVEL: self.battery_level,
        }

    @property
    def is_on(self):
        """ Returns True if switch is on. """
        return self._value == STATE_ON

    def turn_on(self):
        """ Turns the switch on. """
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, 1)
        self._value = STATE_ON
        self.update_ha_state()

    def turn_off(self):
        """ Turns the pin to low/off. """
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, 0)
        self._value = STATE_OFF
        self.update_ha_state()

    def update_sensor(self, value, battery_level):
        """ Update the controller with the latest value from a sensor. """
        _LOGGER.info("%s value = %s", self._name, value)
        if self.value_type == self.const.SetReq.V_TRIPPED or \
           self.value_type == self.const.SetReq.V_ARMED or \
           self.value_type == self.const.SetReq.V_STATUS or \
           self.value_type == self.const.SetReq.V_LIGHT or \
           self.value_type == self.const.SetReq.V_LOCK_STATUS:
            self._value = STATE_ON if int(value) == 1 else STATE_OFF
        else:
            self._value = value
        self.battery_level = battery_level
        self.update_ha_state()
