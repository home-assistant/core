"""
Adds support for generic hygrostat units.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.generic_hygrostat/
"""
import asyncio
import collections
from datetime import timedelta, datetime
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

ATTR_SAMPLES = 'samples'
ATTR_TARGET = 'target'
ATTR_MAX_ON_TIMER = 'max_on_timer'

CONF_SENSOR = 'sensor'
CONF_DELTA_TRIGGER = 'delta_trigger'
CONF_TARGET_OFFSET = 'target_offset'
CONF_MAX_ON_TIME = 'max_on_time'

DEFAULT_DELTA_TRIGGER = 3
DEFAULT_TARGET_OFFSET = 3
DEFAULT_MAX_ON_TIME = timedelta(seconds=7200)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSOR): cv.entity_id,
    vol.Optional(CONF_DELTA_TRIGGER, default=DEFAULT_DELTA_TRIGGER):
        vol.Coerce(float),
    vol.Optional(CONF_TARGET_OFFSET, default=DEFAULT_TARGET_OFFSET):
        vol.Coerce(float),
    vol.Optional(CONF_MAX_ON_TIME, default=DEFAULT_MAX_ON_TIME):
        cv.time_period
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Generic Hygrostat platform."""
    name = config.get(CONF_NAME)
    sensor_id = config.get(CONF_SENSOR)
    delta_trigger = config.get(CONF_DELTA_TRIGGER)
    target_offset = config.get(CONF_TARGET_OFFSET)
    max_on_time = config.get(CONF_MAX_ON_TIME)

    async_add_devices([GenericHygrostat(
        hass, name, sensor_id, delta_trigger, target_offset, max_on_time)])


class GenericHygrostat(Entity):
    """Representation of a Generic Hygrostat device."""

    def __init__(self, hass, name, sensor_id, delta_trigger, target_offset,
                 max_on_time):
        """Initialize the hygrostat."""
        self.hass = hass
        self._name = name
        self.sensor_id = sensor_id
        self.delta_trigger = delta_trigger
        self.target_offset = target_offset
        self.max_on_time = max_on_time

        self.sensor_humidity = None
        self.target = None
        self.samples = collections.deque([], 3)
        self.max_on_timer = None

        self._state = STATE_OFF
        self._icon = 'mdi:water-percent'

        self._async_update()

        async_track_time_interval(hass, self._async_update, SAMPLE_INTERVAL)

    @callback
    def _async_update(self, now=None):
        try:
            self.update_humidity()
        except ValueError as ex:
            _LOGGER.warning(ex)
            return

        if self.calc_delta() >= self.delta_trigger:
            _LOGGER.debug("Humidity rise detected at '%s' with delta '%s'",
                          self.name, self.calc_delta())
            self.set_on()

        if self.target and self.sensor_humidity <= self.target:
            _LOGGER.debug("Dehumidifying target reached for '%s'",
                          self.name)
            self.set_off()

        if self.max_on_timer and self.max_on_timer < datetime.now():
            _LOGGER.debug("Max on timer reached for '%s'",
                          self.name)
            self.set_off()

    def update_humidity(self):
        """Update local humidity state from source sensor."""
        sensor = self.hass.states.get(self.sensor_id)

        if sensor is None:
            raise ValueError("Unknown humidity sensor '{}'".format(
                self.sensor_id))

        if sensor.state == STATE_UNKNOWN:
            raise ValueError("Humidity sensor '{}' has state '{}'".format(
                self.sensor_id, STATE_UNKNOWN))

        try:
            self.sensor_humidity = int(sensor.state)
            self.add_sample(self.sensor_humidity)
        except ValueError:
            raise ValueError(
                "Unable to update humidity from sensor '{}' with value '{}'"
                .format(self.sensor_id, sensor.state))

    def add_sample(self, value):
        """Add given humidity sample to sample shift register."""
        self.samples.append(value)

    def calc_delta(self):
        """Calculate the humidity delta."""
        return self.sensor_humidity - self.get_minimum()

    def get_minimum(self):
        """Return the lowest humidity sample."""
        try:
            return min(self.samples)
        except ValueError:
            return None

    def set_dehumidification_target(self):
        """Setting dehumidification target to min humidity sample + offset."""
        if self.target is None:
            self.target = min(self.samples) + self.target_offset

    def reset_dehumidification_target(self):
        """Unsetting dehumidification target."""
        self.target = None

    def set_state(self, state):
        """Setting hygrostat sensor to given state."""
        if self._state is not state:
            self._state = state
            self.schedule_update_ha_state()

    def set_max_on_timer(self):
        """Setting max on timer."""
        if self.max_on_timer is None:
            self.max_on_timer = datetime.now() + self.max_on_time

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
            ATTR_SAMPLES: list(self.samples),
            ATTR_TARGET: self.target,
            ATTR_MAX_ON_TIMER: self.max_on_timer
        }
