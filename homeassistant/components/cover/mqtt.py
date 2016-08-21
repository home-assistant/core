"""
Support for MQTT cover devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.mqtt/
"""
import logging

import voluptuous as vol

import homeassistant.components.mqtt as mqtt
from homeassistant.components.cover import CoverDevice
from homeassistant.const import CONF_NAME, CONF_VALUE_TEMPLATE
from homeassistant.components.mqtt import (
    CONF_STATE_TOPIC, CONF_COMMAND_TOPIC, CONF_QOS)
from homeassistant.helpers import template
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

CONF_PAYLOAD_OPEN = 'payload_open'
CONF_PAYLOAD_CLOSE = 'payload_close'
CONF_PAYLOAD_STOP = 'payload_stop'

DEFAULT_NAME = "MQTT Cover"
DEFAULT_PAYLOAD_OPEN = "OPEN"
DEFAULT_PAYLOAD_CLOSE = "CLOSE"
DEFAULT_PAYLOAD_STOP = "STOP"

PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PAYLOAD_OPEN, default=DEFAULT_PAYLOAD_OPEN): cv.string,
    vol.Optional(CONF_PAYLOAD_CLOSE, default=DEFAULT_PAYLOAD_CLOSE): cv.string,
    vol.Optional(CONF_PAYLOAD_STOP, default=DEFAULT_PAYLOAD_STOP): cv.string,
})


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Add MQTT Rollershutter."""
    add_devices_callback([MqttRollershutter(
        hass,
        config[CONF_NAME],
        config.get(CONF_STATE_TOPIC),
        config[CONF_COMMAND_TOPIC],
        config[CONF_QOS],
        config[CONF_PAYLOAD_OPEN],
        config[CONF_PAYLOAD_CLOSE],
        config[CONF_PAYLOAD_STOP],
        config.get(CONF_VALUE_TEMPLATE)
    )])


# pylint: disable=abstract-method
# pylint: disable=too-many-arguments, too-many-instance-attributes
class MqttRollershutter(CoverDevice):
    """Representation of a roller shutter that can be controlled using MQTT."""

    def __init__(self, hass, name, state_topic, command_topic, qos,
                 payload_open, payload_close, payload_stop, value_template):
        """Initialize the roller shutter."""
        self._state = None
        self._hass = hass
        self._name = name
        self._state_topic = state_topic
        self._command_topic = command_topic
        self._qos = qos
        self._payload_open = payload_open
        self._payload_close = payload_close
        self._payload_stop = payload_stop

        if self._state_topic is None:
            return

        def message_received(topic, payload, qos):
            """A new MQTT message has been received."""
            if value_template is not None:
                payload = template.render_with_possible_json_value(
                    hass, value_template, payload)
            if payload.isnumeric() and 0 <= int(payload) <= 100:
                self._state = int(payload)
                self.update_ha_state()
            else:
                _LOGGER.warning(
                    "Payload is expected to be an integer between 0 and 100")

        mqtt.subscribe(hass, self._state_topic, message_received, self._qos)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the roller shutter."""
        return self._name

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._state

    def open_cover(self, **kwargs):
        """Move the roller shutter up."""
        mqtt.publish(self.hass, self._command_topic, self._payload_open,
                     self._qos)

    def close_cover(self, **kwargs):
        """Move the roller shutter down."""
        mqtt.publish(self.hass, self._command_topic, self._payload_close,
                     self._qos)

    def stop_cover(self, **kwargs):
        """Stop the device."""
        mqtt.publish(self.hass, self._command_topic, self._payload_stop,
                     self._qos)
