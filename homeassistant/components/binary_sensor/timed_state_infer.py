# """
# Infers its state from the current state and duration of other sensors.
# """
import asyncio
import logging
from datetime import timedelta
import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import CONF_ENTITY_ID, STATE_UNKNOWN, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.core import callback
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.event import track_point_in_time, track_state_change, \
    async_track_state_change, async_track_point_in_time
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_TIME_ON = 'seconds_on'
CONF_TIME_OFF = 'seconds_off'
CONF_VALUE_ON = 'value_on'
CONF_VALUE_OFF = 'value_off'
DEFAULT_NAME = "Timed State Infer Binary Sensor"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_TIME_ON): cv.positive_int,
    vol.Required(CONF_TIME_OFF): cv.positive_int,
    vol.Required(CONF_VALUE_ON): vol.Coerce(float),
    vol.Required(CONF_VALUE_OFF): vol.Coerce(float)
})

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    async_add_devices([TimedStateInferBinarySensor(hass, config[CONF_NAME],
                                                   config[CONF_ENTITY_ID],
                                                   config[CONF_TIME_ON],
                                                   config[CONF_TIME_OFF],
                                                   config[CONF_VALUE_ON],
                                                   config[CONF_VALUE_OFF])])


class TimedStateInferBinarySensor(BinarySensorDevice):
    """Representation of a sensor."""

    def __init__(self, hass, name, observed_entity_id, time_on, time_off,
                 value_on, value_off):
        self._hass = hass
        self._name = name
        self._observed_entity_id = observed_entity_id
        self._time_on = timedelta(seconds=time_on)
        self._time_off = timedelta(seconds=time_off)
        self._value_on = value_on
        self._value_off = value_off
        self._is_on = False
        self._pending = False
        self._pending_since = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._is_on

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Call when entity about to be added."""

        @callback
        def async_sensor_state_listener(entity, old_state, new_state):
            """Handle sensor state changes."""
            self.update_state(new_state.state)

        async_track_state_change(self._hass, self._observed_entity_id,
                                 async_sensor_state_listener)

    @asyncio.coroutine
    def async_pending_expired(self, time):
        device_state = self.hass.states.get(self._observed_entity_id)
        if device_state is None:
            return

        self.update_state(device_state.state)

    def update_state(self, observed_entity_state):
        if observed_entity_state == STATE_UNKNOWN:
            return

        try:
            obs_value = float(observed_entity_state)
        except ValueError:
            _LOGGER.warning("Value cannot be processed as a number: %s",
                            observed_entity_state)
            return

        """If we are already in the correct state, no need to do anything"""
        if self._is_on:
            if obs_value >= self._value_on:
                self._pending = False
                return
        else:
            if obs_value <= self._value_off:
                self._pending = False
                return

        if self._pending:
            time_pending = dt_util.utcnow() - self._pending_since
            if self._is_on:
                time_remaining = time_pending - self._time_off
            else:
                time_remaining = time_pending - self._time_on

            if time_remaining.seconds <= 0:
                self._is_on = not self._is_on
                self._pending = False
                self.schedule_update_ha_state()
        else:
            # enter pending mode (start counting time to change state)
            self._pending_since = dt_util.utcnow()
            self._pending = True

            time_to_expire = dt_util.utcnow() + (
                self._time_off if self._is_on else self._time_on)

            async_track_point_in_time(self._hass, self.async_pending_expired,
                                      time_to_expire)
