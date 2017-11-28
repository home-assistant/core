"""
Calculates the weighted average of a sensor's historical numeric values.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.history_average/
"""
import asyncio
from operator import attrgetter
from collections import defaultdict
import logging
import voluptuous as vol

from homeassistant.core import callback
import homeassistant.components.history as history
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_ENTITY_ID, CONF_UNIT_OF_MEASUREMENT,
    EVENT_HOMEASSISTANT_START)
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'history_average'
DEPENDENCIES = ['history']

CONF_START = 'start'
CONF_END = 'end'
CONF_DURATION = 'duration'
CONF_PERIOD_KEYS = [CONF_START, CONF_END, CONF_DURATION]

DEFAULT_NAME = 'unnamed average'
ICON = 'mdi:chart-line'

ATTR_DURATION = 'duration'


def exactly_two_period_keys(conf):
    """Ensure exactly 2 of CONF_PERIOD_KEYS are provided."""
    provided = 0

    for param in CONF_PERIOD_KEYS:
        if param in conf and conf[param] is not None:
            provided += 1

    if provided != 2:
        raise vol.Invalid('You must provide exactly 2 of the following:'
                          ' start, end, duration')
    return conf


PLATFORM_SCHEMA = vol.All(PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_START, default=None): cv.template,
    vol.Optional(CONF_END, default=None): cv.template,
    vol.Optional(CONF_DURATION, default=None): cv.time_period,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=''): cv.string,
}), exactly_two_period_keys)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices,
                         discovery_info=None):
    """Set up the HistoryAverage sensor."""
    entity_id = config.get(CONF_ENTITY_ID)
    start = config.get(CONF_START)
    end = config.get(CONF_END)
    duration = config.get(CONF_DURATION)
    name = config.get(CONF_NAME)
    unit = config.get(CONF_UNIT_OF_MEASUREMENT)

    for template in [start, end]:
        if template is not None:
            template.hass = hass

    async_add_devices(
        [HistoryAverageSensor(hass, entity_id, start, end, duration,
                              name, unit)])
    return True


class HistoryAverageSensor(Entity):
    """HistoryAverage sensor which calculates time weighted averages."""

    @asyncio.coroutine
    def async_get_history(self):
        """Pull states from recorder history."""
        yield from self.async_update_period()
        start, _end = self._period

        self._history = []

        # get state changes history between start and now
        states = history.state_changes_during_period(
            self._hass, start, None, self._entity_id)
        states = states.get(self._entity_id)
        if states:
            self._history.extend(states)

    @asyncio.coroutine
    def asysnc_trim_history(self):
        """Remove items which are not relevent to the current period."""
        yield from self.async_update_period()
        start, _end = self._period
        start_timestamp = dt_util.as_timestamp(start)

        def after_start(state, timestamp):
            """Test if the State last changed after the timestamp."""
            return state.last_changed.timestamp() >= timestamp

        # remove items before the current period's starting point,
        # keeping the first item before the starting period to enable
        # calculation of the state between start -> next state change
        for index, state in enumerate(self._history[:]):
            if after_start(state, start_timestamp):
                break
            else:
                # remove if the next item is also before start
                next_index = index + 1
                if (next_index < len(self._history) and
                        (not after_start(self._history[next_index],
                                         start_timestamp))):
                    del self._history[index]

    def get_period(self):
        """Return current period, used for testing."""
        return self._period

    def __init__(
            self, hass, entity_id, start, end, duration,
            name, unit):
        """Initialize the HistoryAverage sensor."""
        self._hass = hass
        self._entity_id = entity_id
        self._duration = duration
        self._start = start
        self._end = end
        self._name = name
        self._unit_of_measurement = unit

        # set defaults at init
        now = dt_util.utcnow()
        self._period = (now, now)
        self._history = []
        self._state = 0

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Initialize data and register callbacks."""
        # load data from recorder and do initial calculation
        yield from self.async_get_history()
        yield from self.async_update()

        @callback
        def state_listener(entity, old_state, new_state):
            """Handle the sensor state changes."""
            self._history.append(new_state)
            sorted(self._history, key=attrgetter('last_changed'))
            self._hass.async_add_job(self.async_update_ha_state(True))

        @callback
        def sensor_startup(event):
            """Update on startup."""
            async_track_state_change(
                self._hass, self._entity_id, state_listener)

            self._hass.async_add_job(self.async_update_ha_state(True))

        self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, sensor_startup)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the state is expressed in."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """Return the polling state."""
        # Since the values can/do change with time, not just with
        # state changes, the sensor should poll
        return True

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        def period_in_seconds(period):
            """Get the period period duration in seconds."""
            if len(period) != 2 or period[0] == period[1]:
                return 0.0
            return (period[1] - period[0]).total_seconds()

        def pretty_duration(period):
            """Format a duration in days, hours, minutes, seconds."""
            seconds = period_in_seconds(period)
            days, seconds = divmod(seconds, 86400)
            hours, seconds = divmod(seconds, 3600)
            minutes, seconds = divmod(seconds, 60)
            if days > 0:
                return '%dd %dh %dm' % (days, hours, minutes)
            elif hours > 0:
                return '%dh %dm' % (hours, minutes)
            return '%dm' % minutes

        return {
            ATTR_DURATION: pretty_duration(self._period),
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @asyncio.coroutine
    def async_update(self):
        """Update the sensor's state."""
        # clean up history & update period
        yield from self.asysnc_trim_history()
        start, end = self._period

        _LOGGER.info(" - period start: %s", start)
        _LOGGER.info(" - period end  : %s", end)
        now = dt_util.utcnow()

        # Compute timestamps
        start_timestamp = dt_util.as_timestamp(start)
        end_timestamp = dt_util.as_timestamp(end)
        now_timestamp = dt_util.as_timestamp(now)

        last_state = None
        last_time = None
        total_elapsed = 0
        intervals = defaultdict(float)

        # Sum time spent in each state
        for item in self._history:
            current_state = item.state
            current_time = item.last_changed.timestamp()

            # don't include values not within the period
            if end_timestamp <= current_time:
                break

            # Average over valid states
            if last_state is not None:
                if last_time < start_timestamp:
                    last_time = start_timestamp
                elapsed = current_time - last_time
                total_elapsed += elapsed
                intervals[float(last_state)] += elapsed

            last_time = current_time
            last_state = current_state

        # Count time elapsed between last history state and end of measure
        if last_state is not None:
            measure_end = min(end_timestamp, now_timestamp)
            elapsed = measure_end - last_time
            total_elapsed += elapsed
            intervals[float(last_state)] += elapsed

        # Calculate the weighted average
        updated_state = 0
        for state in intervals:
            updated_state += float(state) * (intervals[state] / total_elapsed)

        self._state = round(updated_state, 2)

    @asyncio.coroutine
    def async_update_period(self):
        """Parse the templates and store a datetime tuple in _period."""
        start = None
        end = None

        def handle_template_exception(ex, field):
            """Log an error nicely if the template cannot be interpreted."""
            if ex.args and ex.args[0].startswith(
                    "UndefinedError: 'None' has no attribute"):
                # Common during HA startup - so just a warning
                _LOGGER.warning("Error parsing template for field %s", field)
                return
            else:
                _LOGGER.exception("Error parsing template for field %s", field)

        # Parse start
        if self._start is not None:
            try:
                start_rendered = self._start.async_render()
            except (TemplateError, TypeError) as ex:
                handle_template_exception(ex, 'start')
                return
            start = dt_util.parse_datetime(start_rendered)

            if start is None:
                try:
                    start = dt_util.utc_from_timestamp(float(start_rendered))
                except ValueError:
                    _LOGGER.error("Parsing error: start must be a datetime"
                                  "or a timestamp")
                    return

        # Parse end
        if self._end is not None:
            try:
                end_rendered = self._end.async_render()
            except (TemplateError, TypeError) as ex:
                handle_template_exception(ex, 'end')
                return
            end = dt_util.parse_datetime(end_rendered)
            if end is None:
                try:
                    end = dt_util.utc_from_timestamp(float(end_rendered))
                except ValueError:
                    _LOGGER.error("Parsing error: end must be a datetime "
                                  "or a timestamp")
                    return

        # Calculate start or end using the duration
        if start is None:
            start = end - self._duration
        if end is None:
            end = start + self._duration

        # Convert times to UTC
        start = dt_util.as_utc(start)
        end = dt_util.as_utc(end)

        self._period = start, end
