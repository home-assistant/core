"""
Support for MQTT switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.mqtt/
"""
import logging

import voluptuous as vol

from homeassistant.components.mqtt import (
    CONF_STATE_TOPIC, CONF_COMMAND_TOPIC, CONF_QOS, CONF_RETAIN)
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (
    CONF_NAME, CONF_OPTIMISTIC, CONF_VALUE_TEMPLATE, CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON)
import homeassistant.components.mqtt as mqtt
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

DEFAULT_NAME = 'MQTT Switch'
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_PAYLOAD_OFF = 'OFF'
DEFAULT_OPTIMISTIC = False

PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the MQTT switch."""
    value_template = config.get(CONF_VALUE_TEMPLATE)
    if value_template is not None:
        value_template.hass = hass
    add_devices([MqttSwitch(
        hass,
        config.get(CONF_NAME),
        config.get(CONF_STATE_TOPIC),
        config.get(CONF_COMMAND_TOPIC),
        config.get(CONF_QOS),
        config.get(CONF_RETAIN),
        config.get(CONF_PAYLOAD_ON),
        config.get(CONF_PAYLOAD_OFF),
        config.get(CONF_OPTIMISTIC),
        value_template,
    )])


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
                payload = value_template.render_with_possible_json_value(
                    payload)
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
            mqtt.subscribe(
                hass, self._state_topic, message_received, self._qos)

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
