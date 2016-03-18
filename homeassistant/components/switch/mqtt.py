"""
Support for MQTT switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.mqtt/
"""
import logging

import homeassistant.components.mqtt as mqtt
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.helpers import template
from homeassistant.util import convert

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT Switch"
DEFAULT_QOS = 0
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OFF = "OFF"
DEFAULT_OPTIMISTIC = False
DEFAULT_RETAIN = False

DEPENDENCIES = ['mqtt']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Add MQTT switch."""
    if config.get('command_topic') is None:
        _LOGGER.error("Missing required variable: command_topic")
        return False

    add_devices_callback([MqttSwitch(
        hass,
        convert(config.get('name'), str, DEFAULT_NAME),
        config.get('state_topic'),
        config.get('command_topic'),
        convert(config.get('qos'), int, DEFAULT_QOS),
        convert(config.get('retain'), bool, DEFAULT_RETAIN),
        convert(config.get('payload_on'), str, DEFAULT_PAYLOAD_ON),
        convert(config.get('payload_off'), str, DEFAULT_PAYLOAD_OFF),
        convert(config.get('optimistic'), bool, DEFAULT_OPTIMISTIC),
        config.get(CONF_VALUE_TEMPLATE))])


# pylint: disable=too-many-arguments, too-many-instance-attributes
class MqttSwitch(SwitchDevice):
    """Representation of a switch that can be toggled using MQTT."""

    def __init__(self, hass, name, state_topic, command_topic, qos, retain,
                 payload_on, payload_off, optimistic, value_template):
        """Initialize the MQTT switch."""
        self._state = False
        self._hass = hass
        self._name = name
        self._state_topic = state_topic
        self._command_topic = command_topic
        self._qos = qos
        self._retain = retain
        self._payload_on = payload_on
        self._payload_off = payload_off
        self._optimistic = optimistic

        def message_received(topic, payload, qos):
            """A new MQTT message has been received."""
            if value_template is not None:
                payload = template.render_with_possible_json_value(
                    hass, value_template, payload)
            if payload == self._payload_on:
                self._state = True
                self.update_ha_state()
            elif payload == self._payload_off:
                self._state = False
                self.update_ha_state()

        if self._state_topic is None:
            # Force into optimistic mode.
            self._optimistic = True
        else:
            mqtt.subscribe(hass, self._state_topic, message_received,
                           self._qos)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    def turn_on(self, **kwargs):
        """Turn the device on."""
        mqtt.publish(self.hass, self._command_topic, self._payload_on,
                     self._qos, self._retain)
        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = True
            self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        mqtt.publish(self.hass, self._command_topic, self._payload_off,
                     self._qos, self._retain)
        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = False
            self.update_ha_state()
