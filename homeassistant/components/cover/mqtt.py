"""
Support for MQTT cover devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.mqtt/
"""
import asyncio
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
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the MQTT Cover."""
    value_template = config.get(CONF_VALUE_TEMPLATE)
    if value_template is not None:
        value_template.hass = hass

    async_add_devices([MqttCover(
        config.get(CONF_NAME),
        config.get(CONF_STATE_TOPIC),
        config.get(CONF_COMMAND_TOPIC),
        config.get(CONF_QOS),
        config.get(CONF_RETAIN),
        config.get(CONF_STATE_OPEN),
        config.get(CONF_STATE_CLOSED),
        config.get(CONF_PAYLOAD_OPEN),
        config.get(CONF_PAYLOAD_CLOSE),
        config.get(CONF_PAYLOAD_STOP),
        config.get(CONF_OPTIMISTIC),
        value_template,
    )])


class MqttCover(CoverDevice):
    """Representation of a cover that can be controlled using MQTT."""

    def __init__(self, name, state_topic, command_topic, qos, retain,
                 state_open, state_closed, payload_open, payload_close,
                 payload_stop, optimistic, value_template):
        """Initialize the cover."""
        self._position = None
        self._state = None
        self._name = name
        self._state_topic = state_topic
        self._command_topic = command_topic
        self._qos = qos
        self._payload_open = payload_open
        self._payload_close = payload_close
        self._payload_stop = payload_stop
        self._state_open = state_open
        self._state_closed = state_closed
        self._retain = retain
        self._optimistic = optimistic or state_topic is None
        self._template = value_template

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Subscribe mqtt events.

        This method is a coroutine.
        """
        @callback
        def message_received(topic, payload, qos):
            """A new MQTT message has been received."""
            if self._template is not None:
                payload = self._template.async_render_with_possible_json_value(
                    payload)

            if payload == self._state_open:
                self._state = False
            elif payload == self._state_closed:
                self._state = True
            elif payload.isnumeric() and 0 <= int(payload) <= 100:
                if int(payload) > 0:
                    self._state = False
                else:
                    self._state = True
                self._position = int(payload)
            else:
                _LOGGER.warning(
                    "Payload is not True, False, or integer (0-100): %s",
                    payload)
                return

            self.hass.async_add_job(self.async_update_ha_state())

        if self._state_topic is None:
            # Force into optimistic mode.
            self._optimistic = True
        else:
            yield from mqtt.async_subscribe(
                self.hass, self._state_topic, message_received, self._qos)

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

    @asyncio.coroutine
    def async_open_cover(self, **kwargs):
        """Move the cover up.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass, self._command_topic, self._payload_open, self._qos,
            self._retain)
        if self._optimistic:
            # Optimistically assume that cover has changed state.
            self._state = False
            self.hass.async_add_job(self.async_update_ha_state())

    @asyncio.coroutine
    def async_close_cover(self, **kwargs):
        """Move the cover down.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass, self._command_topic, self._payload_close, self._qos,
            self._retain)
        if self._optimistic:
            # Optimistically assume that cover has changed state.
            self._state = True
            self.hass.async_add_job(self.async_update_ha_state())

    @asyncio.coroutine
    def async_stop_cover(self, **kwargs):
        """Stop the device.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass, self._command_topic, self._payload_stop, self._qos,
            self._retain)
