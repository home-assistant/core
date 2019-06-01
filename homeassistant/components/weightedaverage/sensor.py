"""
Weighted averages sensor component for Home Assistant.

Calculates an avereage value for another sensor,
that is weighted according to the duration for each individal sensor value.
Also records the maximum and minimum sensor values for the given duration,
as well as the rate at which the sensor value ascends or descends.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.weightedaverage/
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import pytz
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.recorder.util import execute, session_scope
from homeassistant.components.sensor import (DEVICE_CLASSES_SCHEMA,
                                             ENTITY_ID_FORMAT, PLATFORM_SCHEMA)
from homeassistant.const import (ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT,
                                 CONF_DEVICE_CLASS, CONF_ENTITY_ID,
                                 CONF_ICON_TEMPLATE, CONF_NAME,
                                 CONF_UNIT_OF_MEASUREMENT, STATE_UNKNOWN)
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.event import (async_track_point_in_time,
                                         async_track_time_interval)

_LOGGER = logging.getLogger(__name__)

# Sensor attributes
ATTR_COUNT = 'number_of_samples'  # Sensor samples used to calculate average.
ATTR_MAX_VALUE = 'max_value'  # Maximum sensor value sampled.
ATTR_MIN_VALUE = 'min_value'  # Minimum sensor value sampled.
ATTR_SAMPLE_TIME = 'sample_timeframe'  # Duration for sensor value samples.
ATTR_TOP_RATE_ASC = 'top_ascending_rate'  # Top ascending rate for sensor.
ATTR_TOP_RATE_DESC = 'top_descending_rate'  # Top descending rate for sensor.
ATTR_UPDATE_TIME = 'last_update_time'  # Timestamp for last update of average.

# Configuration parameters
#
# Update only at timestamps evenly divided with update interval:
CONF_ONLY_EVEN_TIMESTAMPS = 'at_even_timestamps'
CONF_ROUND_VALUES = 'round_values'  # Number of digits to round the values
CONF_ROUND_RATES = 'round_rates'  # Number of digits to round the rates
CONF_SAMPLE_TIME = 'sample_time'  # Duration for the calculated average.
CONF_SAMPLE_TIME_DAYS = 'days'
CONF_SAMPLE_TIME_HOURS = 'hours'
CONF_SAMPLE_TIME_MINUTES = 'minutes'
CONF_UPDATE_INTERVAL = 'update_interval'  # Update interval for the average.
CONF_UPDATE_INTERVAL_DAYS = 'days'
CONF_UPDATE_INTERVAL_HOURS = 'hours'
CONF_UPDATE_INTERVAL_MINUTES = 'minutes'

DEFAULT_UNIT_OF_MEASUREMENT = ''
DEFAULT_ONLY_EVEN_TIMESTAMPS = True
DEFAULT_SAMPLE_TIME = [{CONF_SAMPLE_TIME_HOURS: 1}]
DEFAULT_UPDATE_INTERVAL = [{CONF_SAMPLE_TIME_MINUTES: 10}]

_SAMPLE_TIME_SCHEMA = vol.Schema({
    vol.Optional(CONF_SAMPLE_TIME_DAYS): vol.Coerce(int),
    vol.Optional(CONF_SAMPLE_TIME_HOURS): vol.Coerce(int),
    vol.Optional(CONF_SAMPLE_TIME_MINUTES): vol.Coerce(int)
})

_UPDATE_INTERVAL_SCHEMA = vol.Schema({
    vol.Optional(CONF_UPDATE_INTERVAL_DAYS): vol.Coerce(int),
    vol.Optional(CONF_UPDATE_INTERVAL_HOURS): vol.Coerce(int),
    vol.Optional(CONF_UPDATE_INTERVAL_MINUTES): vol.Coerce(int)
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT,
                 default=DEFAULT_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_ICON_TEMPLATE): cv.string,
    vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_SAMPLE_TIME,
                 default=DEFAULT_SAMPLE_TIME): [_SAMPLE_TIME_SCHEMA],
    vol.Optional(CONF_UPDATE_INTERVAL,
                 default=DEFAULT_UPDATE_INTERVAL): [_UPDATE_INTERVAL_SCHEMA],
    vol.Optional(CONF_ROUND_VALUES): vol.Coerce(int),
    vol.Optional(CONF_ROUND_RATES): vol.Coerce(int),
    vol.Optional(CONF_ONLY_EVEN_TIMESTAMPS,
                 default=DEFAULT_ONLY_EVEN_TIMESTAMPS): vol.Coerce(bool)
})


def previous_even_time(time_of_day, time_interval):
    """
    Return previous matching.

    Calcalute the previous occasion when the time of day
    could be evenly divided with a given time interval.
    """
    if time_interval.days > 0:
        time_interval_total_seconds = ((time_interval.days * 24 * 3600)
                                       + time_interval.seconds)
        time_of_day_total_seconds = ((time_of_day.day * 24 * 3600)
                                     + (time_of_day.hour * 3600)
                                     + (time_of_day.minute * 60))
    else:
        time_interval_total_seconds = time_interval.seconds
        time_of_day_total_seconds = ((time_of_day.hour * 3600)
                                     + (time_of_day.minute * 60))

    if time_interval_total_seconds > 0:
        divrest = divmod(time_of_day_total_seconds,
                         time_interval_total_seconds)[1]
        time_of_day = (time_of_day - timedelta(seconds=divrest))

    time_of_day = time_of_day.replace(second=0)
    time_of_day = time_of_day.replace(microsecond=0)

    return time_of_day


def next_even_time(time_of_day, time_interval):
    """
    Return next matching time.

    Calcalute the next occasion when the time of day
    can be evenly divided with a given amount of time.
    """
    if time_interval.days > 0:
        time_interval_total_seconds = ((time_interval.days * 24 * 3600)
                                       + time_interval.seconds)
        time_of_day_total_seconds = ((time_of_day.day * 24 * 3600)
                                     + (time_of_day.hour * 3600)
                                     + (time_of_day.minute * 60))
    else:
        time_interval_total_seconds = time_interval.seconds
        time_of_day_total_seconds = ((time_of_day.hour * 3600)
                                     + (time_of_day.minute * 60))

    if time_interval_total_seconds > 0:
        divrest = divmod(time_of_day_total_seconds,
                         time_interval_total_seconds)[1]
        tonext = (time_interval_total_seconds - divrest)
        time_of_day = (time_of_day + timedelta(seconds=tonext))
    else:
        time_of_day = (time_of_day + timedelta(minutes=1))

    time_of_day = time_of_day.replace(second=0)
    time_of_day = time_of_day.replace(microsecond=0)

    return time_of_day


def c_to_k(deg_c):
    """Convert degrees Celcius to Kelvin."""
    return deg_c + 273.15


def k_to_c(deg_k):
    """Convert Kelvin to degrees Celcius."""
    return deg_k - 273.15


def f_to_k(deg_f):
    """Convert degrees Farenheit to Kelvin."""
    return (deg_f + 459.67) * (5/9)


def k_to_f(deg_k):
    """Convert Kelvin to degrees Farenheit."""
    return (deg_k * (9/5)) - 459.67


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Weighted Average sensor."""
    source_entity_id = config.get(CONF_ENTITY_ID)
    name = config.get(CONF_NAME)
    unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
    icon_template = config.get(CONF_ICON_TEMPLATE)
    friendly_name = config.get(ATTR_FRIENDLY_NAME, name)
    device_class = config.get(CONF_DEVICE_CLASS)

    sample_time_list = config.get(CONF_SAMPLE_TIME)
    sample_time = timedelta()
    for tsobj in sample_time_list:
        if CONF_SAMPLE_TIME_DAYS in tsobj:
            sample_time = (sample_time
                           + timedelta(
                               days=tsobj[
                                   CONF_SAMPLE_TIME_DAYS]))
        if CONF_SAMPLE_TIME_HOURS in tsobj:
            sample_time = (sample_time
                           + timedelta(
                               hours=tsobj[
                                   CONF_SAMPLE_TIME_HOURS]))
        if CONF_SAMPLE_TIME_MINUTES in tsobj:
            sample_time = (sample_time
                           + timedelta(
                               minutes=tsobj[
                                   CONF_SAMPLE_TIME_MINUTES]))
    update_interval_list = config.get(CONF_UPDATE_INTERVAL)
    update_interval = timedelta()
    for tsobj in update_interval_list:
        if CONF_UPDATE_INTERVAL_DAYS in tsobj:
            update_interval = (update_interval
                               + timedelta(
                                   days=tsobj[
                                       CONF_UPDATE_INTERVAL_DAYS]))
        if CONF_UPDATE_INTERVAL_HOURS in tsobj:
            update_interval = (update_interval
                               + timedelta(
                                   hours=tsobj[
                                       CONF_UPDATE_INTERVAL_HOURS]))
        if CONF_UPDATE_INTERVAL_MINUTES in tsobj:
            update_interval = (update_interval
                               + timedelta(
                                   minutes=tsobj[
                                       CONF_UPDATE_INTERVAL_MINUTES]))
    update_on_even_timestamps = config.get(CONF_ONLY_EVEN_TIMESTAMPS)
    round_values = config.get(CONF_ROUND_VALUES)
    round_rates = config.get(CONF_ROUND_RATES)

    async_add_devices(
        [WeightedAverageSensor(hass,
                               name,
                               source_entity_id,
                               unit_of_measurement,
                               device_class,
                               icon_template,
                               friendly_name,
                               sample_time,
                               update_interval,
                               update_on_even_timestamps,
                               round_values,
                               round_rates)],
        True)
    return True


class WeightedAverageSensor(Entity):
    """Representation of a Weighted Average sensor."""

    def __init__(self,
                 hass,
                 name,
                 source_entity_id,
                 unit_of_measurement,
                 device_class,
                 icon_template,
                 friendly_name,
                 sample_time,
                 update_interval,
                 update_on_even_timestamps,
                 round_values,
                 round_rates):
        """Initialize the Weighted Average sensor."""
        self._hass = hass
        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, name,
                                                  hass=hass)
        self._source_entity_id = source_entity_id
        self.is_binary = bool(self._source_entity_id.split('.')[0] ==
                              'binary_sensor')
        self._name = friendly_name

        self._unit_of_measurement = unit_of_measurement
        if self._unit_of_measurement == '°C':
            self._is_celcius = True
        else:
            self._is_celcius = False
        if self._unit_of_measurement == '°F':
            self._is_fahrenheit = True
        else:
            self._is_fahrenheit = False

        self._icon = icon_template
        self._device_class = device_class

        self._sample_time = sample_time
        self._update_interval = update_interval
        self._update_on_even_timestamps = update_on_even_timestamps
        self._round_values = round_values
        self._round_rates = round_rates

        self._states_history = []
        self._last_states_update = None

        self.num_states = 0
        self.states_wavg = STATE_UNKNOWN
        self.states_max = STATE_UNKNOWN
        self.states_min = STATE_UNKNOWN
        self.rates_max = STATE_UNKNOWN
        self.rates_min = STATE_UNKNOWN

        @callback
        # pylint: disable=invalid-name
        def async_wavg_sensor_timer(now):
            """Update sensor at set time interval."""
            if self._update_on_even_timestamps:

                #  If average value should one be updated at
                #  timestamps evenly divided with update interval,
                #  perform update as per the previous even timestamp.
                update_timestamp = previous_even_time(
                    now,
                    self._update_interval)
            else:
                #  Else perform update as per current time
                update_timestamp = now

            _LOGGER.debug("update at set time interval for %s at %s",
                          self._source_entity_id, update_timestamp)

            self._get_states_from_database(update_timestamp)

            hass.async_add_job(self.async_update_ha_state, True)

        @callback
        def async_wavg_sensor_timer_first(now):
            """Update at the first interval."""
            if self._update_on_even_timestamps:
                #  If updates are only to be made at timestamps
                #  evenly divided with update interval.
                #  perform update as per the previous even timestamp.
                update_timestamp = previous_even_time(
                    now,
                    self._update_interval)
            else:
                #  Else perform update as per current time
                update_timestamp = now

            _LOGGER.debug(
                "update at the first time interval for %s at %s",
                self._source_entity_id, update_timestamp)

            self._get_states_from_database(update_timestamp)
            hass.async_add_job(self.async_update_ha_state, True)

            _LOGGER.debug(
                "schedule regular updates at time interval %s for %s",
                self._update_interval,
                self._source_entity_id)
            async_track_time_interval(
                hass,
                async_wavg_sensor_timer,
                self._update_interval)

        if 'recorder' in self._hass.config.components:
            thenowtime = datetime.utcnow()
            thenowtime = thenowtime.replace(tzinfo=pytz.UTC)

            if self._update_on_even_timestamps:
                # If updates are only to made at timestamps
                # evenly divided with update interval,
                # perform update as per the previous even timestamp.
                update_timestamp = previous_even_time(thenowtime,
                                                      self._update_interval)
            else:
                # Else perform update as per current time.
                update_timestamp = thenowtime

            _LOGGER.debug(
                "run first update for %s with update time %s",
                self._source_entity_id, update_timestamp)
            self._get_states_from_database(update_timestamp)

            if self._update_on_even_timestamps:
                # If updates are only to made at timestamps
                # evenly divided with update interval,
                # schedule the next update at the next even timestamp.
                thenexttime = next_even_time(thenowtime,
                                             self._update_interval)
                _LOGGER.debug(
                    "schedule next update for %s at %s",
                    self._source_entity_id, thenexttime)
                async_track_point_in_time(
                    hass,
                    async_wavg_sensor_timer_first,
                    thenexttime)
            else:
                # Else just schedule regularar updates at the update interval.
                _LOGGER.debug(
                    "schedule regular updates at time interval %s for %s",
                    self._update_interval,
                    self._source_entity_id)
                async_track_time_interval(
                    hass,
                    async_wavg_sensor_timer,
                    self._update_interval)

        else:
            # The database has to be configured.
            _LOGGER.debug(
                "not scheduling update at set time interval for %s "
                "(no recorder component)",
                self._source_entity_id)

    def _get_states_from_database(self, now):
        """Get the list of states from the database."""
        start_time = (now - self._sample_time)

        from homeassistant.components.recorder.models import States
        _LOGGER.debug("getting states for %s from the database at %s",
                      self._source_entity_id, now)

        self._states_history = []

        with session_scope(hass=self._hass) as session:
            query = session.query(States)\
                .filter(States.entity_id == self._source_entity_id.lower(),
                        States.last_updated <= start_time)\
                .order_by(States.last_updated.desc())\
                .limit(1)
            self._states_history = execute(query)

        if self._states_history:
            self._states_history[0].last_updated = start_time
            self._states_history[0].last_changed = start_time

        with session_scope(hass=self._hass) as session:
            query = session.query(States)\
                .filter(States.entity_id == self._source_entity_id.lower(),
                        States.last_updated > start_time)\
                .order_by(States.last_updated.asc())
            self._states_history.extend(execute(query))

        self._last_states_update = now

        _LOGGER.debug(
            "getting states from database completed for %s",
            self._source_entity_id)

    def _update_from_states(self):
        """Update the weighted average sensor from retrieved states."""
        num_states = len(self._states_history)

        if num_states >= 2:
            weights = []
            states = []
            rates = []
            for scnt in range(1, num_states):
                try:
                    state = float(self._states_history[scnt-1].state)
                    if self._is_celcius:
                        state = c_to_k(state)
                    elif self._is_fahrenheit:
                        state = f_to_k(state)
                    last_time = self._states_history[scnt-1].last_changed
                    this_time = self._states_history[scnt].last_changed
                    this_diff = (this_time - last_time).total_seconds()
                    new_state = float(self._states_history[scnt].state)
                    if self._is_celcius:
                        new_state = c_to_k(new_state)
                    elif self._is_fahrenheit:
                        new_state = f_to_k(new_state)
                    this_rate = ((new_state - state) / this_diff) \
                        if this_diff > 0 \
                        else 0
                    states.append(state)
                    weights.append(this_diff)
                    rates.append(this_rate)

                except (ValueError, TypeError) as ex:
                    _LOGGER.debug(
                        "could not read one state for %s. "
                        "(%s) %s %s %s %s - %s",
                        self._source_entity_id,
                        scnt,
                        self._states_history[scnt-1].state,
                        self._states_history[scnt-1].last_changed,
                        self._states_history[scnt].last_changed,
                        self._states_history[scnt].state,
                        ex)

            try:
                last_state = float(self._states_history[num_states-1].state)
                if self._is_celcius:
                    last_state = c_to_k(last_state)
                elif self._is_fahrenheit:
                    last_state = f_to_k(last_state)
                last_time = self._states_history[num_states-1].last_changed
                last_diff = (self._last_states_update
                             - last_time).total_seconds()
                states.append(last_state)
                weights.append(last_diff)
            except (ValueError, TypeError) as ex:
                _LOGGER.debug(
                    "could not read last state for %s. (%s) %s %s - %s",
                    self._source_entity_id,
                    scnt,
                    self._states_history[num_states-1].state,
                    self._states_history[num_states-1].last_changed,
                    ex)

            self.num_states = len(states)
            if self.num_states >= 1:
                self.states_wavg = (sum(x * y for x, y in zip(states, weights))
                                    / sum(weights))
                self.states_max = max(states)
                self.states_min = min(states)
                if self._is_celcius:
                    self.states_wavg = k_to_c(self.states_wavg)
                    self.states_max = k_to_c(self.states_max)
                    self.states_min = k_to_c(self.states_min)
                elif self._is_fahrenheit:
                    self.states_wavg = k_to_f(self.states_wavg)
                    self.states_max = k_to_f(self.states_max)
                    self.states_min = k_to_f(self.states_min)
                self.rates_max = max(rates) if (max(rates) > 0) else 0
                self.rates_min = min(rates) if (min(rates) < 0) else 0
            else:
                self.states_wavg = STATE_UNKNOWN
                self.states_max = STATE_UNKNOWN
                self.states_min = STATE_UNKNOWN
                self.rates_max = STATE_UNKNOWN
                self.rates_min = STATE_UNKNOWN

        else:
            self.num_states = num_states
            if num_states == 1:
                self.states_wavg = self._states_history[0].state
                self.states_max = self._states_history[0].state
                self.states_min = self._states_history[0].state
                self.rates_max = 0
                self.rates_min = 0
            else:
                self.states_wavg = STATE_UNKNOWN
                self.states_max = STATE_UNKNOWN
                self.states_min = STATE_UNKNOWN
                self.rates_max = STATE_UNKNOWN
                self.rates_min = STATE_UNKNOWN

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.states_wavg if not self.is_binary else STATE_UNKNOWN

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        if not self.is_binary:
            state = {
                ATTR_COUNT: self.num_states,
                ATTR_MAX_VALUE: self.states_max,
                ATTR_MIN_VALUE: self.states_min,
                ATTR_SAMPLE_TIME: str(self._sample_time),
                ATTR_TOP_RATE_ASC: self.rates_max,
                ATTR_TOP_RATE_DESC: self.rates_min,
                ATTR_UNIT_OF_MEASUREMENT: self._unit_of_measurement,
                ATTR_UPDATE_TIME: datetime.strftime(
                    self._last_states_update,
                    "%Y-%m-%d %H:%M:%S%z"),
            }
            return state

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("update triggered for %s",
                      self._source_entity_id)

        if not self.is_binary:
            if self._states_history:
                self._update_from_states()
                try:
                    self.states_wavg = round(self.states_wavg,
                                             self._round_values)
                except (ValueError, TypeError):
                    pass
                try:
                    self.rates_max = round(self.rates_max,
                                           self._round_rates)
                except (ValueError, TypeError):
                    pass
                try:
                    self.rates_min = round(self.rates_min,
                                           self._round_rates)
                except (ValueError, TypeError):
                    pass
            else:
                self.num_states = self.states_wavg = STATE_UNKNOWN
                self.states_min = self.states_max = STATE_UNKNOWN
                self.rates_max = self.rates_min = STATE_UNKNOWN
