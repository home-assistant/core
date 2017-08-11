"""
Support for monitoring if a sensor value is below/above a threshold.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.threshold/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA, DEVICE_CLASSES_SCHEMA)
from homeassistant.const import (
    CONF_NAME, CONF_ENTITY_ID, CONF_TYPE, STATE_UNKNOWN,
    ATTR_ENTITY_ID, CONF_DEVICE_CLASS)
from homeassistant.core import callback
from homeassistant.helpers.event import (
    async_track_state_change, async_track_point_in_utc_time)

_LOGGER = logging.getLogger(__name__)

ATTR_SENSOR_VALUE = 'sensor_value'
ATTR_THRESHOLD = 'threshold'
ATTR_TYPE = 'type'

CONF_LOWER = 'lower'
CONF_THRESHOLD = 'threshold'
CONF_UPPER = 'upper'
CONF_ON_DELAY = 'on_delay'
CONF_OFF_DELAY = 'off_delay'

DEFAULT_NAME = 'Threshold'

SENSOR_TYPES = [CONF_LOWER, CONF_UPPER]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_THRESHOLD): vol.Coerce(float),
    vol.Required(CONF_TYPE): vol.In(SENSOR_TYPES),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_ON_DELAY): vol.All(
        cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_OFF_DELAY): vol.All(
        cv.time_period, cv.positive_timedelta),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Threshold sensor."""
    entity_id = config.get(CONF_ENTITY_ID)
    name = config.get(CONF_NAME)
    threshold = config.get(CONF_THRESHOLD)
    limit_type = config.get(CONF_TYPE)
    device_class = config.get(CONF_DEVICE_CLASS)
    on_delay = config.get(CONF_ON_DELAY)
    off_delay = config.get(CONF_OFF_DELAY)

    async_add_devices(
        [ThresholdSensor(hass, entity_id, name, threshold, limit_type,
                         device_class, on_delay, off_delay)], True)
    return True


class ThresholdSensor(BinarySensorDevice):
    """Representation of a Threshold sensor."""

    def __init__(self, hass, entity_id, name, threshold, limit_type,
                 device_class, on_delay, off_delay):
        """Initialize the Threshold sensor."""
        self._hass = hass
        self._entity_id = entity_id
        self.is_upper = limit_type == 'upper'
        self._name = name
        self._threshold = threshold
        self._device_class = device_class
        self._on_delay = on_delay
        self._off_delay = off_delay
        self._deviation = False  # The state ignoring delays
        self._state = False  # The actual state of the sensor
        self.sensor_value = 0
        self._async_remove_delay_listener = None

        @callback
        # pylint: disable=invalid-name
        def async_threshold_sensor_state_listener(
                entity, old_state, new_state):
            """Handle sensor state changes."""
            if new_state.state == STATE_UNKNOWN:
                return

            def change_state(new_state):
                """Change the threshold sensor's state."""
                self._state = new_state
                self._hass.async_add_job(self.async_update_ha_state)

            def clear_listener():
                """Clear active timer listener."""
                if self._async_remove_delay_listener is not None:
                    self._async_remove_delay_listener()
                    self._async_remove_delay_listener = None

            try:
                self.sensor_value = float(new_state.state)
            except ValueError:
                _LOGGER.error("State is not numerical")

            old_deviation = self._deviation
            if self.is_upper:
                self._deviation = bool(self.sensor_value > self._threshold)
            else:
                self._deviation = bool(self.sensor_value < self._threshold)

            if ((self._deviation and self._on_delay is None) or
                    (not self._deviation and self._off_delay is None)):
                change_state(self._deviation)
                return

            # We only need to reset and set up new timers if the deviation
            # changed
            if old_deviation != self._deviation:
                @callback
                def threshold_delay_listener(now):
                    """Fire on state changes after a delay and calls action."""
                    self._async_remove_delay_listener = None
                    clear_listener()
                    change_state(self._deviation)

                # cleanup previous listener
                clear_listener()

                if self._deviation:
                    time_delta = self._on_delay
                else:
                    time_delta = self._off_delay

                self._async_remove_delay_listener = \
                    async_track_point_in_utc_time(
                        hass,
                        threshold_delay_listener,
                        dt_util.utcnow() + time_delta)

            # Always trigger a state update event so that the attributes get
            # updated
            self._hass.async_add_job(self.async_update_ha_state)

        async_track_state_change(
            hass, entity_id, async_threshold_sensor_state_listener)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_class(self):
        """Return the sensor class of the sensor."""
        return self._device_class

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ENTITY_ID: self._entity_id,
            ATTR_SENSOR_VALUE: self.sensor_value,
            ATTR_THRESHOLD: self._threshold,
            ATTR_TYPE: CONF_UPPER if self.is_upper else CONF_LOWER,
        }
