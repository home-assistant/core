# -*- coding: utf-8 -*-
"""
homeassistant.components.sensor.mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure a MQTT sensor.

This generic sensor implementation uses the MQTT message payload as the sensor value.

sensor:
  platform: mqtt
  name: "MQTT Sensor"
  state_topic: "home/bedroom/temperature"
  unit_of_measurement: "ºC"

Variables:

name
*Optional
The name of the sensor. Default is 'MQTT Sensor'.

state_topic
*Required
The MQTT topic subscribed to receive sensor values. 

unit_of_measurement
*Optional
Defines the units of measurement of the sensor, if any.

"""

import logging
from homeassistant.helpers.entity import Entity
import homeassistant.components.mqtt as mqtt

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT Sensor"

DEPENDENCIES = ['mqtt']

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Add MQTT Sensor """
    
    if config.get('state_topic') is None:
        _LOGGER.error("Missing required variable: state_topic")
        return False
        
    add_devices_callback([MqttSensor(
        hass,
        config.get('name',DEFAULT_NAME),
        config.get('state_topic'),
        config.get('unit_of_measurement'))])


class MqttSensor(Entity):
    """ Represents a sensor that can be updated using MQTT """
    def __init__(self, hass, name, state_topic, unit_of_measurement):
        self._state = "-"
        self._hass = hass
        self._name = name
        self._state_topic = state_topic
        self._unit_of_measurement = unit_of_measurement

        def message_received(topic, payload, qos):
            self._state = payload
            self.update_ha_state()

        mqtt.subscribe(hass, self._state_topic, message_received)

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
