"""
Support for MQTT cover devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.mqtt/
"""
import logging

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.components.mqtt as mqtt
from homeassistant.components.cover import CoverDevice
from homeassistant.const import (
    CONF_NAME, CONF_VALUE_TEMPLATE, CONF_OPTIMISTIC, STATE_OPEN,
    STATE_CLOSED)
from homeassistant.components.mqtt import (
    CONF_STATE_TOPIC, CONF_COMMAND_TOPIC, CONF_QOS, CONF_RETAIN)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

CONF_PAYLOAD_OPEN = 'payload_open'
CONF_PAYLOAD_CLOSE = 'payload_close'
CONF_PAYLOAD_STOP = 'payload_stop'
CONF_STATE_OPEN = 'state_open'
CONF_STATE_CLOSED = 'state_closed'

CONF_TILT_STATE_TOPIC = 'tilt_state_topic'
CONF_TILT_COMMAND_TOPIC = 'tilt_command_topic'
CONF_TILT_PAYLOAD_OPEN = 'tilt_payload_open'
CONF_TILT_PAYLOAD_CLOSE = 'tilt_payload_close'
CONF_TILT_PAYLOAD_STOP = 'tilt_payload_stop'
CONF_TILT_STATE_OPEN = 'tilt_state_open'
CONF_TILT_STATE_CLOSED = 'tilt_state_closed'

CONF_TILT_OPTIMISTIC = 'tilt_optimistic'

CONF_TILT_VALUE_TEMPLATE = 'tilt_value_template'

DEFAULT_NAME = 'MQTT Cover'
DEFAULT_PAYLOAD_OPEN = 'OPEN'
DEFAULT_PAYLOAD_CLOSE = 'CLOSE'
DEFAULT_PAYLOAD_STOP = 'STOP'
DEFAULT_OPTIMISTIC = False
DEFAULT_RETAIN = False

PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PAYLOAD_OPEN, default=DEFAULT_PAYLOAD_OPEN): cv.string,
    vol.Optional(CONF_PAYLOAD_CLOSE, default=DEFAULT_PAYLOAD_CLOSE): cv.string,
    vol.Optional(CONF_PAYLOAD_STOP, default=DEFAULT_PAYLOAD_STOP): cv.string,
    vol.Optional(CONF_STATE_OPEN, default=STATE_OPEN): cv.string,
    vol.Optional(CONF_STATE_CLOSED, default=STATE_CLOSED): cv.string,
    vol.Required(CONF_TILT_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_TILT_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_TILT_PAYLOAD_OPEN,
                 default=DEFAULT_PAYLOAD_OPEN): cv.string,
    vol.Optional(CONF_TILT_PAYLOAD_CLOSE,
                 default=DEFAULT_PAYLOAD_CLOSE): cv.string,
    vol.Optional(CONF_TILT_PAYLOAD_STOP,
                 default=DEFAULT_PAYLOAD_STOP): cv.string,
    vol.Optional(CONF_TILT_STATE_OPEN,
                 default=STATE_OPEN): cv.string,
    vol.Optional(CONF_TILT_STATE_CLOSED,
                 default=STATE_CLOSED): cv.string,
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
    vol.Optional(CONF_TILT_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
    vol.Optional(CONF_TILT_VALUE_TEMPLATE): cv.template,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the MQTT Cover."""
    value_template = config.get(CONF_VALUE_TEMPLATE)
    if value_template is not None:
        value_template.hass = hass
    tilt_value_template = config.get(CONF_TILT_VALUE_TEMPLATE)
    if tilt_value_template is not None:
        tilt_value_template.hass = hass
    add_devices([MqttCover(
        hass,
        config.get(CONF_NAME),
        config.get(CONF_STATE_TOPIC),
        config.get(CONF_COMMAND_TOPIC),
        config.get(CONF_TILT_STATE_TOPIC),
        config.get(CONF_TILT_COMMAND_TOPIC),
        config.get(CONF_QOS),
        config.get(CONF_RETAIN),
        config.get(CONF_STATE_OPEN),
        config.get(CONF_STATE_CLOSED),
        config.get(CONF_PAYLOAD_OPEN),
        config.get(CONF_PAYLOAD_CLOSE),
        config.get(CONF_PAYLOAD_STOP),
        config.get(CONF_TILT_STATE_OPEN),
        config.get(CONF_TILT_STATE_CLOSED),
        config.get(CONF_TILT_PAYLOAD_OPEN),
        config.get(CONF_TILT_PAYLOAD_CLOSE),
        config.get(CONF_TILT_PAYLOAD_STOP),
        config.get(CONF_OPTIMISTIC),
        config.get(CONF_TILT_OPTIMISTIC),
        value_template,
        tilt_value_template,
    )])


class MqttCover(CoverDevice):
    """Representation of a cover that can be controlled using MQTT."""

    def __init__(self, hass, name, state_topic, command_topic,
                 tilt_state_topic, tilt_command_topic, qos,
                 retain, state_open, state_closed, payload_open, payload_close,
                 payload_stop, tilt_state_open, tilt_state_closed,
                 tilt_payload_open, tilt_payload_close, tilt_payload_stop,
                 optimistic, tilt_optimistic, value_template,
                 tvt):
        """Initialize the cover."""
        self._position = None
        self._state = None
        self._tilt_position = None
        self._tilt_state = None
        self._hass = hass
        self._name = name
        self._state_topic = state_topic
        self._command_topic = command_topic
        self._tilt_state_topic = tilt_state_topic
        self._tilt_command_topic = tilt_command_topic
        self._qos = qos
        self._payload_open = payload_open
        self._payload_close = payload_close
        self._payload_stop = payload_stop
        self._state_open = state_open
        self._state_closed = state_closed
        self._tilt_payload_open = tilt_payload_open
        self._tilt_payload_close = tilt_payload_close
        self._tilt_payload_stop = tilt_payload_stop
        self._tilt_state_open = tilt_state_open
        self._tilt_state_closed = tilt_state_closed
        self._retain = retain
        self._optimistic = optimistic or state_topic is None
        self._tilt_optimistic = tilt_optimistic or tilt_state_topic is None

        @callback
        def message_received(topic, payload, qos):
            """A new MQTT message has been received."""
            if value_template is not None:
                payload = value_template.async_render_with_possible_json_value(
                    payload)
            if payload == self._state_open:
                self._state = False
                hass.async_add_job(self.async_update_ha_state())
            elif payload == self._state_closed:
                self._state = True
                hass.async_add_job(self.async_update_ha_state())
            elif payload.isnumeric() and 0 <= int(payload) <= 100:
                if int(payload) > 0:
                    self._state = False
                else:
                    self._state = True
                self._position = int(payload)
                hass.async_add_job(self.async_update_ha_state())
            else:
                _LOGGER.warning(
                    "Payload is not True, False, or integer (0-100): %s",
                    payload)

        if self._state_topic is None:
            # Force into optimistic mode.
            self._optimistic = True
        else:
            mqtt.subscribe(hass, self._state_topic, message_received,
                           self._qos)

        @callback
        def tilt_message_received(topic, payload, qos):
            """A new tilt MQTT message has been received."""
            if tvt is not None:
                payload = tvt.async_render_with_possible_json_value(
                    payload)
            if payload == self._tilt_state_open:
                self._tilt_state = False
                hass.async_add_job(self.async_update_ha_state())
            elif payload == self._tilt_state_closed:
                self._tilt_state = True
                hass.async_add_job(self.async_update_ha_state())
            elif payload.isnumeric() and 0 <= int(payload) <= 100:
                if int(payload) > 0:
                    self._tilt_state = False
                else:
                    self._tilt_state = True
                self._tilt_position = int(payload)
                hass.async_add_job(self.async_update_ha_state())
            else:
                _LOGGER.warning(
                    "Tilt Payload is not True, False, or integer (0-100): %s",
                    payload)

        if self._tilt_state_topic is None:
            # Force into optimistic mode.
            self._tilt_optimistic = True
        else:
            mqtt.subscribe(hass, self._tilt_state_topic, tilt_message_received,
                           self._qos)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._state

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._position

    @property
    def current_cover_tilt_position(self):
        """Return the current tilt position of the cover."""
        return self._tilt_position

    def open_cover(self, **kwargs):
        """Move the cover up."""
        mqtt.publish(self.hass, self._command_topic, self._payload_open,
                     self._qos, self._retain)
        if self._optimistic:
            # Optimistically assume that cover has changed state.
            self._state = False
            self.schedule_update_ha_state()

    def open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        mqtt.publish(self.hass, self._tilt_command_topic,
                     self._tilt_payload_open, self._qos, self._retain)
        if self._tilt_optimistic:
            # Optimistically assume that cover has changed state.
            self._tilt_state = False
            self.update_ha_state()

    def close_cover(self, **kwargs):
        """Move the cover down."""
        mqtt.publish(self.hass, self._command_topic, self._payload_close,
                     self._qos, self._retain)
        if self._optimistic:
            # Optimistically assume that cover has changed state.
            self._state = True
            self.schedule_update_ha_state()

    def close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        mqtt.publish(self.hass, self._tilt_command_topic,
                     self._tilt_payload_close, self._qos, self._retain)
        if self._tilt_optimistic:
            # Optimistically assume that cover has changed state.
            self._tilt_state = True
            self.update_ha_state()

    def stop_cover(self, **kwargs):
        """Stop the device."""
        mqtt.publish(self.hass, self._command_topic, self._payload_stop,
                     self._qos, self._retain)

    def stop_cover_tilt(self, **kwargs):
        """Stop the cover tilt."""
        mqtt.publish(self.hass, self._tilt_command_topic,
                     self._tilt_payload_stop, self._qos, self._retain)

    def set_cover_position(self, position, **kwargs):
        """Move the cover to a specific position."""
        mqtt.publish(self.hass, self._command_topic, position,
                     self._qos, self._retain)
        if self._optimistic:
            # Optimistically assume that cover has changed state.
            self._state = False
            self._position = position
            self.update_ha_state()

    def set_cover_tilt_position(self, tilt_position, **kwargs):
        """Move the cover til to a specific position."""
        mqtt.publish(self.hass, self._tilt_command_topic, tilt_position,
                     self._qos, self._retain)
        if self._tilt_optimistic:
            # Optimistically assume that cover has changed state.
            self._tilt_state = False
            self._tilt_position = tilt_position
            self.update_ha_state()
