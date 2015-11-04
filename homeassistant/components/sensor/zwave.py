"""
homeassistant.components.sensor.zwave
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Interfaces with Z-Wave sensors.

For more details about the zwave component, please refer to the documentation
at https://home-assistant.io/components/zwave.html
"""
# pylint: disable=import-error
from openzwave.network import ZWaveNetwork
from pydispatch import dispatcher

import homeassistant.components.zwave as zwave
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, STATE_ON, STATE_OFF,
    TEMP_CELCIUS, TEMP_FAHRENHEIT, ATTR_LOCATION)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up Z-Wave sensors. """
    node = zwave.NETWORK.nodes[discovery_info[zwave.ATTR_NODE_ID]]
    value = node.values[discovery_info[zwave.ATTR_VALUE_ID]]

    value.set_change_verified(False)

    # if 1 in groups and (zwave.NETWORK.controller.node_id not in
    #                     groups[1].associations):
    #     node.groups[1].add_association(zwave.NETWORK.controller.node_id)
    print("ZWave sensor type value:", value.command_class)
    if value.command_class == zwave.COMMAND_CLASS_SENSOR_BINARY:
        add_devices([ZWaveBinarySensor(value)])

    elif value.command_class == zwave.COMMAND_CLASS_SENSOR_MULTILEVEL:
        add_devices([ZWaveMultilevelSensor(value)])

    elif value.command_class ==  zwave.COMMAND_CLASS_SENSOR_ALARM:
        print("ZWave sensor type : alarm sensor")
        add_devices([ZWaveAlarmSensor(value)])        

    elif value.command_class == zwave.COMMAND_CLASS_SILENCE_ALARM:
        print("ZWave sensor type : slience alarm")
        add_devices([ZWaveAlarmSensor(value)])        

class ZWaveSensor(Entity):
    """ Represents a Z-Wave sensor. """
    def __init__(self, sensor_value):
        self._value = sensor_value
        self._node = sensor_value.node

        dispatcher.connect(
            self._value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED)

    @property
    def should_poll(self):
        """ False because we will push our own state to HA when changed. """
        return False

    @property
    def unique_id(self):
        """ Returns a unique id. """
        return "ZWAVE-{}-{}".format(self._node.node_id, self._value.object_id)

    @property
    def name(self):
        """ Returns the name of the device. """
        name = self._node.name or "{} {}".format(
            self._node.manufacturer_name, self._node.product_name)

        return "{} {}".format(name, self._value.label)

    @property
    def state(self):
        """ Returns the state of the sensor. """
        return self._value.data

    @property
    def state_attributes(self):
        """ Returns the state attributes. """
        attrs = {
            zwave.ATTR_NODE_ID: self._node.node_id,
        }

        battery_level = self._node.get_battery_level()

        if battery_level is not None:
            attrs[ATTR_BATTERY_LEVEL] = battery_level

        location = self._node.location

        if location:
            attrs[ATTR_LOCATION] = location

        return attrs

    @property
    def unit_of_measurement(self):
        return self._value.units

    def _value_changed(self, value):
        """ Called when a value has changed on the network. """
        if self._value.value_id == value.value_id:
            self.update_ha_state()


# pylint: disable=too-few-public-methods
class ZWaveBinarySensor(ZWaveSensor):
    """ Represents a binary sensor within Z-Wave. """

    @property
    def state(self):
        """ Returns the state of the sensor. """
        return STATE_ON if self._value.data else STATE_OFF


class ZWaveMultilevelSensor(ZWaveSensor):
    """ Represents a multi level sensor Z-Wave sensor. """

    @property
    def state(self):
        """ Returns the state of the sensor. """
        value = self._value.data

        if self._value.units in ('C', 'F'):
            return round(value, 1)
        elif isinstance(value, float):
            return round(value, 2)

        return value

    @property
    def unit_of_measurement(self):
        unit = self._value.units

        if unit == 'C':
            return TEMP_CELCIUS
        elif unit == 'F':
            return TEMP_FAHRENHEIT
        else:
            return unit


class ZWaveAlarmSensor(ZWaveSensor):
    """ Represents a alarm sensor Z-Wave sensor. """

    @property
    def state(self):
        """ Returns the state of the sensor. """
        #value = self._value.data
        return STATE_ON if self._value.data else STATE_OFF
        
