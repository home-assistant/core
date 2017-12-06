"""
Support for MQTT binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.mqtt/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.components.mqtt as mqtt
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, DEVICE_CLASSES_SCHEMA)
from homeassistant.const import (
    CONF_NAME, CONF_VALUE_TEMPLATE, CONF_PAYLOAD_ON, CONF_PAYLOAD_OFF,
    CONF_DEVICE_CLASS)
from homeassistant.components.mqtt import (
    CONF_STATE_TOPIC, CONF_AVAILABILITY_TOPIC, CONF_QOS, valid_subscribe_topic)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_PAYLOAD_AVAILABLE = 'payload_available'
CONF_PAYLOAD_NOT_AVAILABLE = 'payload_not_available'

DEFAULT_NAME = 'MQTT Binary sensor'
DEFAULT_PAYLOAD_OFF = 'OFF'
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_PAYLOAD_AVAILABLE = 'online'
DEFAULT_PAYLOAD_NOT_AVAILABLE = 'offline'

DEPENDENCIES = ['mqtt']

PLATFORM_SCHEMA = mqtt.MQTT_RO_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_AVAILABILITY_TOPIC): valid_subscribe_topic,
    vol.Optional(CONF_PAYLOAD_AVAILABLE,
                 default=DEFAULT_PAYLOAD_AVAILABLE): cv.string,
    vol.Optional(CONF_PAYLOAD_NOT_AVAILABLE,
                 default=DEFAULT_PAYLOAD_NOT_AVAILABLE): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the MQTT binary sensor."""
    if discovery_info is not None:
        config = PLATFORM_SCHEMA(discovery_info)

    value_template = config.get(CONF_VALUE_TEMPLATE)
    if value_template is not None:
        value_template.hass = hass

    async_add_devices([MqttBinarySensor(
        config.get(CONF_NAME),
        config.get(CONF_STATE_TOPIC),
        config.get(CONF_AVAILABILITY_TOPIC),
        config.get(CONF_DEVICE_CLASS),
        config.get(CONF_QOS),
        config.get(CONF_PAYLOAD_ON),
        config.get(CONF_PAYLOAD_OFF),
        config.get(CONF_PAYLOAD_AVAILABLE),
        config.get(CONF_PAYLOAD_NOT_AVAILABLE),
        value_template
    )])


class MqttBinarySensor(BinarySensorDevice):
    """Representation a binary sensor that is updated by MQTT."""

    def __init__(self, name, state_topic, availability_topic, device_class,
                 qos, payload_on, payload_off, payload_available,
                 payload_not_available, value_template):
        """Initialize the MQTT binary sensor."""
        self._name = name
        self._state = None
        self._state_topic = state_topic
        self._availability_topic = availability_topic
        self._available = True if availability_topic is None else False
        self._device_class = device_class
        self._payload_on = payload_on
        self._payload_off = payload_off
        self._payload_available = payload_available
        self._payload_not_available = payload_not_available
        self._qos = qos
        self._template = value_template

    def async_added_to_hass(self):
        """Subscribe mqtt events.

        This method must be run in the event loop and returns a coroutine.
        """
        @callback
        def state_message_received(topic, payload, qos):
            """Handle a new received MQTT state message."""
            if self._template is not None:
                payload = self._template.async_render_with_possible_json_value(
                    payload)
            if payload == self._payload_on:
                self._state = True
            elif payload == self._payload_off:
                self._state = False

            self.async_schedule_update_ha_state()

        yield from mqtt.async_subscribe(
            self.hass, self._state_topic, state_message_received, self._qos)

        @callback
        def availability_message_received(topic, payload, qos):
            """Handle a new received MQTT availability message."""
            if payload == self._payload_available:
                self._available = True
            elif payload == self._payload_not_available:
                self._available = False

            self.async_schedule_update_ha_state()

        if self._availability_topic is not None:
            yield from mqtt.async_subscribe(
                self.hass, self._availability_topic,
                availability_message_received, self._qos)

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def available(self) -> bool:
        """Return if the binary sensor is available."""
        return self._available

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class
