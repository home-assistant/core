"""
Adds support for generic hygrostat units.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.generic_hygrostat/
"""
import asyncio
import collections
import time
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.climate import PLATFORM_SCHEMA
from homeassistant.const import (STATE_ON, STATE_OFF, STATE_UNKNOWN, CONF_NAME)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['sensor']

SAMPLE_INTERVAL = timedelta(minutes=5)

DEFAULT_NAME = 'Generic Hygrostat'

ATTR_HUMIDITY_SENSOR_ID = 'humidity_sensor'
ATTR_HUMIDITY_DELTA_TRIGGER = 'humidity_delta_trigger'
ATTR_HUMIDITY_TARGET_OFFSET = 'humidity_target_offset'
ATTR_MAX_ON_TIME = 'max_on_time'
ATTR_SENSOR_HUMIDITY = 'sensor_humidity'
ATTR_HUMIDITY_TARGET = 'humidity_target'
ATTR_HUMIDITY_SAMPLES = 'humidity_samples'
ATTR_MAX_ON_TIMER = 'max_on_timer'

CONF_HUMIDITY_SENSOR = 'humidity_sensor'
CONF_HUMIDITY_DELTA_TRIGGER = 'humidity_delta_trigger'
CONF_HUMIDITY_TARGET_OFFSET = 'humidity_target_offset'
CONF_MAX_ON_TIME = 'max_on_time'

DEFAULT_HUMIDITY_DELTA_TRIGGER = 3
DEFAULT_HUMIDITY_TARGET_OFFSET = 3
DEFAULT_MAX_ON_TIME = 7200

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HUMIDITY_SENSOR): cv.entity_id,
    vol.Optional(CONF_HUMIDITY_DELTA_TRIGGER,
                 default=DEFAULT_HUMIDITY_DELTA_TRIGGER):
                 vol.Coerce(float),
    vol.Optional(CONF_HUMIDITY_TARGET_OFFSET,
                 default=DEFAULT_HUMIDITY_TARGET_OFFSET):
                 vol.Coerce(float),
    vol.Optional(CONF_MAX_ON_TIME, default=DEFAULT_MAX_ON_TIME):
                 vol.Coerce(float)
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Generic Hygrostat platform."""
    name = config.get(CONF_NAME)
    humidity_sensor_id = config.get(CONF_HUMIDITY_SENSOR)
    humidity_delta_trigger = config.get(CONF_HUMIDITY_DELTA_TRIGGER)
    humidity_target_offset = config.get(CONF_HUMIDITY_TARGET_OFFSET)
    max_on_time = config.get(CONF_MAX_ON_TIME)

    async_add_devices([GenericHygrostat(
        hass, name, humidity_sensor_id, humidity_delta_trigger,
        humidity_target_offset, max_on_time)])


class GenericHygrostat(Entity):
    """Representation of a Generic Hygrostat device."""

    def __init__(self, hass, name, humidity_sensor_id, humidity_delta_trigger,
                 humidity_target_offset, max_on_time):
        """Initialize the hygrostat."""
        self.hass = hass
        self._name = name
        self.humidity_sensor_id = humidity_sensor_id
        self.humidity_delta_trigger = humidity_delta_trigger
        self.humidity_target_offset = humidity_target_offset
        self.max_on_time = max_on_time

        self.sensor_humidity = None
        self.humidity_target = None
        self.humidity_samples = collections.deque([], 3)
        self.max_on_timer = None

        self._state = STATE_OFF
        self._icon = 'mdi:water-percent'

        self._async_update()

        async_track_time_interval(hass, self._async_update,
                                  SAMPLE_INTERVAL)

    @callback
    def _async_update(self, now=None):
        try:
            self.update_humidity()
        except ValueError as ex:
            _LOGGER.warning(ex)
            return

        if self.calc_humidity_delta() >= self.humidity_delta_trigger:
            _LOGGER.debug("Humidity rise detected at '%s' with delta '%s'",
                          self.name, self.calc_humidity_delta())
            self.set_on()

        if self.humidity_target \
                and self.sensor_humidity <= self.humidity_target:
            _LOGGER.debug("Dehumidifying target reached for '%s'",
                          self.name)
            self.set_off()

        if self.max_on_timer and self.max_on_timer < time.time():
            _LOGGER.debug("Max on timer reached for '%s'",
                          self.name)
            self.set_off()

    def update_humidity(self):
        """Update local humidity state from source sensor."""
        sensor = self.hass.states.get(self.humidity_sensor_id)

        if sensor is None:
            raise ValueError("Unknown humidity sensor '{}'".format(
                self.humidity_sensor_id))

        if sensor.state == STATE_UNKNOWN:
            raise ValueError("Humidity sensor '{}' has state '{}'".format(
                self.humidity_sensor_id, STATE_UNKNOWN))

        try:
            self.sensor_humidity = int(sensor.state)
            self.add_humidity_sample(self.sensor_humidity)
        except ValueError:
            raise ValueError(
                "Unable to update humidity from sensor '{}' with value '{}'"
                .format(self.humidity_sensor_id, sensor.state))

    def add_humidity_sample(self, value):
        """Add given humidity sample to sample shift register."""
        self.humidity_samples.append(value)

    def calc_humidity_delta(self):
        """Calculate the humidity delta."""
        return self.sensor_humidity - self.get_humidity_minimum()

    def get_humidity_minimum(self):
        """Return the lowest humidity sample."""
        try:
            return min(self.humidity_samples)
        except ValueError as ex:
            return None

    def set_dehumidification_target(self):
        """Setting dehumidification target to min humidity sample + offset."""
        self.humidity_target = \
            min(self.humidity_samples) + self.humidity_target_offset

    def reset_dehumidification_target(self):
        """Unsetting dehumidification target."""
        self.humidity_target = None

    def set_state(self, state):
        """Setting hygrostat sensor to given state."""
        if self._state is not state:
            self._state = state
            self.schedule_update_ha_state()

    def set_max_on_timer(self):
        """Setting max on timer."""
        self.max_on_timer = time.time() + self.max_on_time

    def reset_max_on_timer(self):
        """Unsetting max on timer."""
        self.max_on_timer = None

    def set_on(self):
        """Setting hygrostat to on."""
        self.set_state(STATE_ON)
        self.set_dehumidification_target()
        self.set_max_on_timer()

    def set_off(self):
        """Setting hygrostat to off."""
        self.set_state(STATE_OFF)
        self.reset_dehumidification_target()
        self.reset_max_on_timer()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def state_attributes(self):
        """Return the attributes of the entity."""
        return {
            ATTR_HUMIDITY_SENSOR_ID: self.humidity_sensor_id,
            ATTR_HUMIDITY_DELTA_TRIGGER: self.humidity_delta_trigger,
            ATTR_HUMIDITY_TARGET_OFFSET: self.humidity_target_offset,
            ATTR_MAX_ON_TIME: self.max_on_time,

            ATTR_SENSOR_HUMIDITY: self.sensor_humidity,
            ATTR_HUMIDITY_TARGET: self.humidity_target,
            ATTR_HUMIDITY_SAMPLES: list(self.humidity_samples),
            ATTR_MAX_ON_TIMER: self.max_on_timer
        }
