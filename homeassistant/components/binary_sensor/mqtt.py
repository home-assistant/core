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
    CONF_SENSOR_CLASS, CONF_DEVICE_CLASS)
from homeassistant.components.mqtt import (CONF_STATE_TOPIC, CONF_QOS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.deprecation import get_deprecated

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'MQTT Binary sensor'
DEFAULT_PAYLOAD_OFF = 'OFF'
DEFAULT_PAYLOAD_ON = 'ON'
DEPENDENCIES = ['mqtt']

PLATFORM_SCHEMA = mqtt.MQTT_RO_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_SENSOR_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
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
        get_deprecated(config, CONF_DEVICE_CLASS, CONF_SENSOR_CLASS),
        config.get(CONF_QOS),
        config.get(CONF_PAYLOAD_ON),
        config.get(CONF_PAYLOAD_OFF),
        value_template
    )])


class MqttBinarySensor(BinarySensorDevice):
    """Representation a binary sensor that is updated by MQTT."""

    def __init__(self, name, state_topic, device_class, qos, payload_on,
                 payload_off, value_template):
        """Initialize the MQTT binary sensor."""
        self._name = name
        self._state = False
        self._state_topic = state_topic
        self._device_class = device_class
        self._payload_on = payload_on
        self._payload_off = payload_off
        self._qos = qos
        self._template = value_template

    def async_added_to_hass(self):
        """Subscribe mqtt events.

        This method must be run in the event loop and returns a coroutine.
        """
        @callback
        def message_received(topic, payload, qos):
            """Handle a new received MQTT message."""
            if self._template is not None:
                payload = self._template.async_render_with_possible_json_value(
                    payload)
            if payload == self._payload_on:
                self._state = True
            elif payload == self._payload_off:
                self._state = False

            self.hass.async_add_job(self.async_update_ha_state())

        return mqtt.async_subscribe(
            self.hass, self._state_topic, message_received, self._qos)

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class
