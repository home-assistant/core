"""
Support for MQTT sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mqtt/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.mqtt import CONF_STATE_TOPIC, CONF_QOS
from homeassistant.const import (
    CONF_FORCE_UPDATE, CONF_NAME, CONF_VALUE_TEMPLATE, STATE_UNKNOWN,
    CONF_UNIT_OF_MEASUREMENT)
from homeassistant.helpers.entity import Entity
import homeassistant.components.mqtt as mqtt
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_EXPIRE_AFTER = 'expire_after'

DEFAULT_NAME = 'MQTT Sensor'
DEFAULT_FORCE_UPDATE = False
DEPENDENCIES = ['mqtt']

PLATFORM_SCHEMA = mqtt.MQTT_RO_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_EXPIRE_AFTER): cv.positive_int,
    vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up MQTT Sensor."""
    if discovery_info is not None:
        config = PLATFORM_SCHEMA(discovery_info)

    value_template = config.get(CONF_VALUE_TEMPLATE)
    if value_template is not None:
        value_template.hass = hass

    async_add_devices([MqttSensor(
        config.get(CONF_NAME),
        config.get(CONF_STATE_TOPIC),
        config.get(CONF_QOS),
        config.get(CONF_UNIT_OF_MEASUREMENT),
        config.get(CONF_FORCE_UPDATE),
        config.get(CONF_EXPIRE_AFTER),
        value_template,
    )])


class MqttSensor(Entity):
    """Representation of a sensor that can be updated using MQTT."""

    def __init__(self, name, state_topic, qos, unit_of_measurement,
                 force_update, expire_after, value_template):
        """Initialize the sensor."""
        self._state = STATE_UNKNOWN
        self._name = name
        self._state_topic = state_topic
        self._qos = qos
        self._unit_of_measurement = unit_of_measurement
        self._force_update = force_update
        self._template = value_template
        self._expire_after = expire_after
        self._expiration_trigger = None

    def async_added_to_hass(self):
        """Subscribe to MQTT events.

        This method must be run in the event loop and returns a coroutine.
        """
        @callback
        def message_received(topic, payload, qos):
            """Handle new MQTT messages."""
            # auto-expire enabled?
            if self._expire_after is not None and self._expire_after > 0:
                # Reset old trigger
                if self._expiration_trigger:
                    self._expiration_trigger()
                    self._expiration_trigger = None

                # Set new trigger
                expiration_at = (
                    dt_util.utcnow() + timedelta(seconds=self._expire_after))

                self._expiration_trigger = async_track_point_in_utc_time(
                    self.hass, self.value_is_expired, expiration_at)

            if self._template is not None:
                payload = self._template.async_render_with_possible_json_value(
                    payload, self._state)
            self._state = payload
            self.async_schedule_update_ha_state()

        return mqtt.async_subscribe(
            self.hass, self._state_topic, message_received, self._qos)

    @callback
    def value_is_expired(self, *_):
        """Triggered when value is expired."""
        self._expiration_trigger = None
        self._state = STATE_UNKNOWN
        self.async_schedule_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def force_update(self):
        """Force update."""
        return self._force_update

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state
