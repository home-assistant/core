# -*- coding: utf-8 -*-
"""
homeassistant.components.switch.mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure a MQTT switch.

In an ideal scenario, the MQTT device will have a state topic to publish
state changes. If these messages are published with RETAIN flag, the MQTT
switch will receive an instant state update after subscription and will
start with correct state. Otherwise, the initial state of the switch will
be false/off.

When a state topic is not available, the switch will work in optimistic mode.
In this mode, the switch will immediately change state after every command.
Otherwise, the switch will wait for state confirmation from device
(message from state_topic).

Optimistic mode can be forced, even if state topic is available.
Try to enable it, if experiencing incorrect switch operation.


Configuration:

switch:
  platform: mqtt
  name: "Bedroom Switch"
  state_topic: "home/bedroom/switch1"
  command_topic: "home/bedroom/switch1/set"
  qos: 0
  payload_on: "ON"
  payload_off: "OFF"
  optimistic: false

Variables:

name
*Optional
The name of the switch. Default is 'MQTT Switch'.

state_topic
*Optional
The MQTT topic subscribed to receive state updates.
If not specified, optimistic mode will be forced.

command_topic
*Required
The MQTT topic to publish commands to change the switch state.

qos
*Optional
The maximum QoS level of the state topic. Default is 0.
This QoS will also be used to publishing messages.

payload_on
*Optional
The payload that represents enabled state. Default is "ON".

payload_off
*Optional
The payload that represents disabled state. Default is "OFF".

optimistic
*Optional
Flag that defines if switch works in optimistic mode. Default is false.

"""

import logging
import homeassistant.components.mqtt as mqtt
from homeassistant.components.switch import SwitchDevice

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT Switch"
DEFAULT_QOS = 0
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OFF = "OFF"
DEFAULT_OPTIMISTIC = False

DEPENDENCIES = ['mqtt']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Add MQTT Switch """

    if config.get('command_topic') is None:
        _LOGGER.error("Missing required variable: command_topic")
        return False

    add_devices_callback([MqttSwitch(
        hass,
        config.get('name', DEFAULT_NAME),
        config.get('state_topic'),
        config.get('command_topic'),
        config.get('qos', DEFAULT_QOS),
        config.get('payload_on', DEFAULT_PAYLOAD_ON),
        config.get('payload_off', DEFAULT_PAYLOAD_OFF),
        config.get('optimistic', DEFAULT_OPTIMISTIC))])


# pylint: disable=too-many-arguments, too-many-instance-attributes
class MqttSwitch(SwitchDevice):
    """ Represents a switch that can be togggled using MQTT """
    def __init__(self, hass, name, state_topic, command_topic, qos,
                 payload_on, payload_off, optimistic):
        self._state = False
        self._hass = hass
        self._name = name
        self._state_topic = state_topic
        self._command_topic = command_topic
        self._qos = qos
        self._payload_on = payload_on
        self._payload_off = payload_off
        self._optimistic = optimistic

        def message_received(topic, payload, qos):
            """ A new MQTT message has been received. """
            if payload == self._payload_on:
                self._state = True
                self.update_ha_state()
            elif payload == self._payload_off:
                self._state = False
                self.update_ha_state()

        if self._state_topic is None:
            # force optimistic mode
            self._optimistic = True
        else:
            # subscribe the state_topic
            mqtt.subscribe(hass, self._state_topic, message_received,
                           self._qos)

    @property
    def should_poll(self):
        """ No polling needed """
        return False

    @property
    def name(self):
        """ The name of the switch """
        return self._name

    @property
    def is_on(self):
        """ True if device is on. """
        return self._state

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        mqtt.publish(self.hass, self._command_topic, self._payload_on,
                     self._qos)
        if self._optimistic:
            # optimistically assume that switch has changed state
            self._state = True
            self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        mqtt.publish(self.hass, self._command_topic, self._payload_off,
                     self._qos)
        if self._optimistic:
            # optimistically assume that switch has changed state
            self._state = False
            self.update_ha_state()
