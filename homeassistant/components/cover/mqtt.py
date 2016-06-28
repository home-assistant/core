"""
Support for MQTT covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.mqtt/
"""
import logging

import homeassistant.components.mqtt as mqtt
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.cover import CoverDevice
from homeassistant.components.mqtt import (
    CONF_STATE_TOPIC, CONF_COMMAND_TOPIC, CONF_QOS, CONF_RETAIN)
from homeassistant.const import (
    CONF_NAME, CONF_OPTIMISTIC, CONF_VALUE_TEMPLATE, STATE_OPEN, STATE_CLOSED,
    SERVICE_OPEN, SERVICE_CLOSE)
from homeassistant.helpers import template

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

CONF_STATE_OPEN = 'state_open'
CONF_STATE_CLOSED = 'state_closed'
CONF_SERVICE_OPEN = 'service_open'
CONF_SERVICE_CLOSE = 'service_close'

DEFAULT_NAME = 'MQTT Cover'
DEFAULT_OPTIMISTIC = False
DEFAULT_RETAIN = False


PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
    vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
    vol.Optional(CONF_STATE_OPEN, default=STATE_OPEN): cv.string,
    vol.Optional(CONF_STATE_CLOSED, default=STATE_CLOSED): cv.string,
    vol.Optional(CONF_SERVICE_OPEN, default=SERVICE_OPEN): cv.string,
    vol.Optional(CONF_SERVICE_CLOSE, default=SERVICE_CLOSE): cv.string
})


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Add MQTT cover."""
    add_devices_callback([MqttCover(
        hass,
        config[CONF_NAME],
        config.get(CONF_STATE_TOPIC),
        config[CONF_COMMAND_TOPIC],
        config[CONF_QOS],
        config[CONF_RETAIN],
        config[CONF_STATE_OPEN],
        config[CONF_STATE_CLOSED],
        config[CONF_SERVICE_OPEN],
        config[CONF_SERVICE_CLOSE],
        config[CONF_OPTIMISTIC],
        config.get(CONF_VALUE_TEMPLATE))])


# pylint: disable=too-many-arguments, too-many-instance-attributes
class MqttCover(CoverDevice):
    """Representation of a MQTT cover."""

    def __init__(self, hass, name, state_topic, command_topic, qos, retain,
                 state_open, state_closed, service_open, service_close,
                 optimistic, value_template):
        """Initialize the cover."""
        self._hass = hass
        self._name = name
        self._state_topic = state_topic
        self._command_topic = command_topic
        self._qos = qos
        self._retain = retain
        self._state_open = state_open
        self._state_closed = state_closed
        self._service_open = service_open
        self._service_close = service_close
        self._optimistic = optimistic or state_topic is None
        self._state = False

        def message_received(topic, payload, qos):
            """A new MQTT message has been received."""
            if value_template is not None:
                payload = template.render_with_possible_json_value(
                    hass, value_template, payload)
            if payload == self._state_open:
                self._state = True
                self.update_ha_state()
            elif payload == self._state_closed:
                self._state = False
                self.update_ha_state()

        if self._state_topic is None:
            # Force into optimistic mode.
            self._optimistic = True
        else:
            mqtt.subscribe(hass, self._state_topic, message_received,
                           self._qos)

    @property
    def name(self):
        """Return the name of the cover if any."""
        return self._name

    @property
    def is_open(self):
        """Return true if cover is open."""
        return self._state == STATE_OPEN

    @property
    def is_closed(self):
        """Return true if cover is closed."""
        return self._state == STATE_CLOSED

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    def close_cover(self):
        """Close the cover."""
        mqtt.publish(self.hass, self._command_topic, self._service_close,
                     self._qos, self._retain)
        if self._optimistic:
            # Optimistically assume that door has changed state.
            self._state = False
            self.update_ha_state()

    def open_cover(self):
        """Open the cover."""
        mqtt.publish(self.hass, self._command_topic, self._service_open,
                     self._qos, self._retain)
        if self._optimistic:
            # Optimistically assume that door has changed state.
            self._state = True
            self.update_ha_state()
