# -*- coding: utf-8 -*-
"""
homeassistant.components.sensor.mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure a MQTT sensor.

This generic sensor implementation uses the MQTT message payload
as the sensor value. If messages in this state_topic are published
with RETAIN flag, the sensor will receive an instant update with
last known value. Otherwise, the initial state will be undefined.

sensor:
  platform: mqtt
  name: "MQTT Sensor"
  state_topic: "home/bedroom/temperature"
  qos: 0
  unit_of_measurement: "ºC"

Variables:

name
*Optional
The name of the sensor. Default is 'MQTT Sensor'.

state_topic
*Required
The MQTT topic subscribed to receive sensor values.

qos
*Optional
The maximum QoS level of the state topic. Default is 0.

unit_of_measurement
*Optional
Defines the units of measurement of the sensor, if any.

"""

import logging
from homeassistant.helpers.entity import Entity
import homeassistant.components.mqtt as mqtt

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT Sensor"
DEFAULT_QOS = 0

DEPENDENCIES = ['mqtt']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Add MQTT Sensor """

    if config.get('state_topic') is None:
        _LOGGER.error("Missing required variable: state_topic")
        return False

    add_devices_callback([MqttSensor(
        hass,
        config.get('name', DEFAULT_NAME),
        config.get('state_topic'),
        config.get('qos', DEFAULT_QOS),
        config.get('unit_of_measurement'))])


# pylint: disable=too-many-arguments, too-many-instance-attributes
class MqttSensor(Entity):
    """ Represents a sensor that can be updated using MQTT """
    def __init__(self, hass, name, state_topic, qos, unit_of_measurement):
        self._state = "-"
        self._hass = hass
        self._name = name
        self._state_topic = state_topic
        self._qos = qos
        self._unit_of_measurement = unit_of_measurement

        def message_received(topic, payload, qos):
            """ A new MQTT message has been received. """
            self._state = payload
            self.update_ha_state()

        mqtt.subscribe(hass, self._state_topic, message_received, self._qos)

    @property
    def should_poll(self):
        """ No polling needed """
        return False

    @property
    def name(self):
        """ The name of the sensor """
        return self._name

    @property
    def unit_of_measurement(self):
        """ Unit this state is expressed in. """
        return self._unit_of_measurement

    @property
    def state(self):
        """ Returns the state of the entity. """
        return self._state
