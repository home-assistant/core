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
from homeassistant.components.cover import CoverDevice, ATTR_TILT_POSITION
from homeassistant.const import (
    CONF_NAME, CONF_VALUE_TEMPLATE, CONF_OPTIMISTIC, STATE_OPEN,
    STATE_CLOSED, STATE_UNKNOWN)
from homeassistant.components.mqtt import (
    CONF_STATE_TOPIC, CONF_COMMAND_TOPIC, CONF_QOS, CONF_RETAIN)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

CONF_TILT_COMMAND_TOPIC = 'tilt_command_topic'
CONF_TILT_STATUS_TOPIC = 'tilt_status_topic'

CONF_PAYLOAD_OPEN = 'payload_open'
CONF_PAYLOAD_CLOSE = 'payload_close'
CONF_PAYLOAD_STOP = 'payload_stop'
CONF_PAYLOAD_TILT = 'payload_tilt'
CONF_STATE_OPEN = 'state_open'
CONF_STATE_CLOSED = 'state_closed'
CONF_TILT_CLOSED_POSITION = 'tilt_closed_value'
CONF_TILT_OPEN_POSITION = 'tilt_opened_value'
CONF_DEVICE_CLASS = 'device_class'
CONF_TILT_MIN = 'tilt_min'
CONF_TILT_MAX = 'tilt_max'

DEFAULT_NAME = 'MQTT Cover'
DEFAULT_PAYLOAD_OPEN = 'OPEN'
DEFAULT_PAYLOAD_CLOSE = 'CLOSE'
DEFAULT_PAYLOAD_STOP = 'STOP'
DEFAULT_PAYLOAD_TILT = 'TILT'
DEFAULT_OPTIMISTIC = False
DEFAULT_RETAIN = False
DEFAULT_TILT_CLOSED_POSITION = '0'
DEFAULT_TILT_OPEN_POSITION = '100'
DEFAULT_DEVICE_CLASS = 'window'
DEFAULT_TILT_MIN = '0'
DEFAULT_TILT_MAX = '100'

PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PAYLOAD_OPEN, default=DEFAULT_PAYLOAD_OPEN): cv.string,
    vol.Optional(CONF_PAYLOAD_CLOSE, default=DEFAULT_PAYLOAD_CLOSE): cv.string,
    vol.Optional(CONF_PAYLOAD_STOP, default=DEFAULT_PAYLOAD_STOP): cv.string,
    vol.Optional(CONF_PAYLOAD_TILT, default=DEFAULT_PAYLOAD_TILT): cv.string,
    vol.Optional(CONF_STATE_OPEN, default=STATE_OPEN): cv.string,
    vol.Optional(CONF_STATE_CLOSED, default=STATE_CLOSED): cv.string,
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
    vol.Optional(CONF_TILT_CLOSED_POSITION,
                 default=DEFAULT_TILT_CLOSED_POSITION): cv.string,
    vol.Optional(CONF_TILT_OPEN_POSITION,
                 default=DEFAULT_TILT_OPEN_POSITION): cv.string,
    vol.Optional(CONF_DEVICE_CLASS,
                 default=DEFAULT_DEVICE_CLASS): cv.string,
    vol.Optional(CONF_TILT_MIN,
                 default=DEFAULT_TILT_MIN): cv.string,
    vol.Optional(CONF_TILT_MAX,
                 default=DEFAULT_TILT_MAX): cv.string,
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
        config.get(CONF_TILT_COMMAND_TOPIC),
        config.get(CONF_TILT_STATUS_TOPIC),
        config.get(CONF_QOS),
        config.get(CONF_RETAIN),
        config.get(CONF_STATE_OPEN),
        config.get(CONF_STATE_CLOSED),
        config.get(CONF_PAYLOAD_OPEN),
        config.get(CONF_PAYLOAD_CLOSE),
        config.get(CONF_PAYLOAD_STOP),
        config.get(CONF_PAYLOAD_TILT),
        config.get(CONF_OPTIMISTIC),
        value_template,
        config.get(CONF_TILT_OPEN_POSITION),
        config.get(CONF_TILT_CLOSED_POSITION),
        config.get(CONF_DEVICE_CLASS),
        config.get(CONF_TILT_MIN),
        config.get(CONF_TILT_MAX),
    )])


class MqttCover(CoverDevice):
    """Representation of a cover that can be controlled using MQTT."""

    def __init__(self, name, state_topic, command_topic, tilt_command_topic,
                 tilt_status_topic, qos, retain, state_open, state_closed,
                 payload_open, payload_close, payload_stop, payload_tilt,
                 optimistic, value_template, tilt_open_position,
                 tilt_closed_position, device_class, tilt_min, tilt_max):
        """Initialize the cover."""
        if tilt_command_topic is not None:
            _LOGGER.info("MQTT cover configured with tilt topic: "
                         + tilt_command_topic)
        self._position = None
        self._state = None
        self._name = name
        self._state_topic = state_topic
        self._command_topic = command_topic
        self._tilt_command_topic = tilt_command_topic
        self._tilt_status_topic = tilt_status_topic
        self._qos = qos
        self._payload_open = payload_open
        self._payload_close = payload_close
        self._payload_stop = payload_stop
        self._payload_tilt = payload_tilt
        self._state_open = state_open
        self._state_closed = state_closed
        self._retain = retain
        self._tilt_open_position = tilt_open_position
        self._tilt_closed_position = tilt_closed_position
        self._optimistic = optimistic or state_topic is None
        self._template = value_template
        self._device_class = device_class
        self._tilt_value = STATE_UNKNOWN
        self._tilt_min = int(tilt_min)
        self._tilt_max = int(tilt_max)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Subscribe mqtt events.

        This method is a coroutine.
        """
        @callback
        def tilt_updated(topic, payload, qos):
            """The tilt was updated."""
            if (payload.isnumeric() and
                    self._tilt_min <= int(payload)
                    and int(payload) <= self._tilt_max):
                tilt_range = self._tilt_max - self._tilt_min
                level = round(float(payload) / tilt_range * 100.0)
                self._tilt_value = level
                _LOGGER.info("Tilt value set to " + str(self._tilt_value))
                self.schedule_update_ha_state()

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

        if self._tilt_status_topic is not None:
            yield from mqtt.async_subscribe(
                self.hass, self._tilt_status_topic, tilt_updated, self._qos)

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
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

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

    @asyncio.coroutine
    def async_open_cover_tilt(self, **kwargs):
        """Tilt the cover open."""
        mqtt.async_publish(self.hass, self._tilt_command_topic,
                           self._tilt_open_position, self._qos, self._retain)

    @asyncio.coroutine
    def async_close_cover_tilt(self, **kwargs):
        """Tilt the cover closed."""
        mqtt.async_publish(self.hass, self._tilt_command_topic,
                           self._tilt_closed_position, self._qos, self._retain)

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt."""
        return self._tilt_value

    def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        if ATTR_TILT_POSITION in kwargs:
            position = float(kwargs[ATTR_TILT_POSITION])

            #The position needs to be between min and max
            tilt_range = self._tilt_max - self._tilt_min
            percentage = position / 100.0
            level = round(tilt_range * percentage)

            _LOGGER.info("setting tilt value to " + str(level))
            mqtt.async_publish(self.hass, self._tilt_command_topic,
                               level, self._qos, self._retain)
