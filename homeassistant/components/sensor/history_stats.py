"""
Component to make instant statistics about your history.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.history_stats/
"""

import asyncio
import logging
import math
import re
import time

import voluptuous as vol

import homeassistant.components.history as history
import homeassistant.components.recorder as recorder
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_ENTITY_ID, CONF_STATE)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'history_stats'
DEPENDENCIES = ['history']

CONF_START = 'start'
CONF_END = 'end'
CONF_DURATION = 'duration'
CONF_PERIOD_KEYS = [CONF_START, CONF_END, CONF_DURATION]

DEFAULT_NAME = 'unnamed statistics'
UNIT = 'h'
UNIT_RATIO = '%'
ICON = 'mdi:chart-line'

PRINT_START = 'from'
PRINT_END = 'to'
PRINT_VALUE = 'value'
PRINT_RATIO = 'ratio'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_STATE): cv.slug,
    vol.Optional(CONF_START, default=None): cv.template,
    vol.Optional(CONF_END, default=None): cv.template,
    vol.Optional(CONF_DURATION, default=None): cv.template,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


# noinspection PyUnusedLocal
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the History Stats sensor."""
    entity_id = config.get(CONF_ENTITY_ID)
    entity_state = config.get(CONF_STATE)
    start = config.get(CONF_START)
    end = config.get(CONF_END)
    duration = config.get(CONF_DURATION)
    name = config.get(CONF_NAME)
    hsh = HistoryStatsHelper

    params = 0
    for param in [start, end, duration]:
        if param is not None:
            params += 1

    if params != 2:
        raise _LOGGER.error('You must provide exactly 2 of the following:' +
                            ' start, end, duration')

    for template in [start, end, duration]:
        if template is not None:
            template.hass = hass
            template.template = hsh.parse_time_expr(template.template)
            # pylint: disable=protected-access
            template._compiled_code = None  # Force recompilation

    yield from async_add_devices([HistoryStatsSensor(
        hass, entity_id, entity_state, start, end, duration, name)], True)
    return True


class HistoryStatsSensor(Entity):
    """Representation of a HistoryStats sensor."""

    def __init__(
            self, hass, entity_id, entity_state, start, end, duration, name):
        """Initialize the HistoryStats sensor."""
        self._hass = hass

        self._entity_id = entity_id
        self._entity_state = entity_state
        self._duration = duration
        self._start = start
        self._end = end
        self._name = name
        self._unit_of_measurement = UNIT

        self._period = (0.0, 0.0)
        self.value = 0

        # noinspection PyUnusedLocal
        # pylint: disable=invalid-name
        @callback
        def async_stats_sensor_state_listener(entity, old_state, new_state):
            """Called when the sensor changes state."""
            hass.async_add_job(self.async_update_ha_state, True)

        async_track_state_change(
            hass, entity_id, async_stats_sensor_state_listener)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(self.value, 2)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """Polling required."""
        return True

    @property
    def state_attributes(self):
        """Return the state attributes of the sensor."""
        start_timestamp, end_timestamp = self._period
        hsh = HistoryStatsHelper
        return {
            PRINT_VALUE: hsh.pretty_duration(self.value),
            PRINT_RATIO: hsh.pretty_ratio(self.value, self._period),
            PRINT_START: hsh.pretty_datetime(start_timestamp),
            PRINT_END: hsh.pretty_datetime(end_timestamp),
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data and updates the states."""
        # Parse templates
        self.update_period()

        # Convert timestamps to dates
        start_timestamp, end_timestamp = self._period
        start = dt_util.utc_from_timestamp(start_timestamp)
        end = dt_util.utc_from_timestamp(end_timestamp)

        if not HistoryStatsHelper.wait_till_db_ready():
            _LOGGER.error('Cannot connect to database')
            return

        # Get history between start and end
        history_list = history.state_changes_during_period(
            start, end, str(self._entity_id))

        if self._entity_id not in history_list.keys():
            return

        # Get the first state
        last_state = history.get_state(start, self._entity_id)
        last_state = (last_state is not None and
                      last_state == self._entity_state)
        last_time = start_timestamp
        elapsed = 0

        # Make calculations
        for item in history_list.get(self._entity_id):
            current_state = item.state == self._entity_state
            current_time = item.last_changed.timestamp()

            if last_state:
                elapsed += current_time - last_time

            last_state = current_state
            last_time = current_time

        # Save value in hours
        self.value = elapsed / 3600

    def update_period(self):
        """Parse the templates and store a timestamp tuple in _period."""
        start = None
        end = None
        duration = None

        try:
            if self._start is not None:
                start = math.floor(float(self._start.async_render()))
            if self._end is not None:
                end = math.floor(float(self._end.async_render()))
            if self._duration is not None:
                duration = math.floor(float(self._duration.async_render()))
        except TemplateError as ex:
            HistoryStatsHelper.handle_template_exception(ex)
        except ValueError:
            _LOGGER.error('Template value cannot be converted to timestamp ')

        # Calculate start or end using the duration
        start = end - duration if start is None else start
        end = start + duration if end is None else end

        self._period = start, end


class HistoryStatsHelper:
    """Static methods to make the HistoryStatsSensor code lighter."""

    @staticmethod
    def parse_time_expr(expression):
        """Replace time expressions with functions accepted by templates."""
        regex = r"(_NOW_(\.replace\([a-z]+=[0-9]+\))*)"
        replacement = r"as_timestamp(\1)"

        return re.sub(
            regex, replacement, expression.replace("_THIS_DAY_", "_TODAY_")
            .replace("_ONE_WEEK_", "604800")
            .replace("_ONE_DAY_", "86400")
            .replace("_ONE_HOUR_", "3600")
            .replace("_ONE_MINUTE_", "60")
            .replace("_THIS_YEAR_", "_THIS_MONTH_.replace(month=1)")
            .replace("_THIS_MONTH_", "_TODAY_.replace(day=1)")
            .replace("_THIS_WEEK_", "_TODAY_ - now().weekday() * 86400")
            .replace("_TODAY_", "_THIS_HOUR_.replace(hour=0)")
            .replace("_THIS_HOUR_", "_THIS_MINUTE_.replace(minute=0)")
            .replace("_THIS_MINUTE_", "_NOW_.replace(second=0)")) \
            .replace("_NOW_", "now()")

    @staticmethod
    def pretty_datetime(timestamp):
        """Format a timestamp to a formatted datetime in the local timezone."""
        return dt_util.as_local(dt_util.utc_from_timestamp(timestamp)) \
            .strftime('%Y/%m/%d %H:%M:%S')

    @staticmethod
    def pretty_duration(hours):
        """Format a duration in days, hours, minutes, seconds."""
        seconds = int(3600 * hours)
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        if days > 0:
            return '%dd %dh %dm %ds' % (days, hours, minutes, seconds)
        elif hours > 0:
            return '%dh %dm %ds' % (hours, minutes, seconds)
        elif minutes > 0:
            return '%dm %ds' % (minutes, seconds)
        else:
            return '%ds' % (seconds,)

    @staticmethod
    def pretty_ratio(value, period):
        """Format the ratio of value / period duration."""
        if len(period) != 2:
            return

        ratio = 3600 * 100 * value / (period[1] - period[0])
        return str(round(ratio, 1)) + UNIT_RATIO

    @staticmethod
    def handle_template_exception(ex):
        """Log an error nicely if the template cannot be interpreted."""
        if ex.args and ex.args[0].startswith(
                "UndefinedError: 'None' has no attribute"):
            # Common during HA startup - so just a warning
            _LOGGER.warning(ex)
            return
        _LOGGER.error(ex)

    # noinspection PyProtectedMember
    # pylint: disable=protected-access
    @staticmethod
    def wait_till_db_ready():
        """Start recorder connection if not done already."""
        # Without this method, the recorder does not start its connection
        # itself, resulting in an infinite loop blocking the boot of home
        # assistant. It may be a nasty bug.
        if recorder._INSTANCE.db_ready._flag:
            return True
        time.sleep(0.5)  # Wait, just in case db is starting
        if recorder._INSTANCE.db_ready._flag:
            return True
        recorder._INSTANCE._setup_connection()  # Force connection
        time.sleep(0.5)  # Wait a little
        return recorder._INSTANCE.db_ready._flag
