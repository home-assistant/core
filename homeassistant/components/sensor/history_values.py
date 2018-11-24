"""
Show values from the history in a sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.history_values/
"""

import datetime
from decimal import Decimal
import logging
import math

import voluptuous as vol

from homeassistant.components import history
from homeassistant.components.sensor import ENTITY_ID_FORMAT, PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_AT, CONF_NAME, CONF_TYPE, CONF_UNIT_OF_MEASUREMENT,
    EVENT_STATE_CHANGED, STATE_UNKNOWN)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.event import async_track_time_change
import homeassistant.util.dt as dt_util

DEPENDENCIES = [history.DOMAIN]

DOMAIN = 'history_values'

_LOGGER = logging.getLogger(__name__)

ATTR_NEW_STATE = 'new_state'

CONF_START = 'start'
CONF_END = 'end'
CONF_DURATION = 'duration'

CONF_HOURS = 'hours'
CONF_MINUTES = 'minutes'
CONF_SECONDS = 'seconds'
CONF_PERIOD_KEYS = [CONF_START, CONF_END, CONF_DURATION]

CONF_TARGET_ENTITY = 'target_entity_id'
CONF_UPDATE = 'update'

TYPE_AVG = 'average'
TYPE_LOW = 'low'
TYPE_PEAK = 'peak'
TYPE_RANGE = 'range'


def exactly_two_period_keys(conf):
    """Ensure exactly 2 of CONF_PERIOD_KEYS are provided."""
    if sum(param in conf for param in CONF_PERIOD_KEYS) != 2:
        raise vol.Invalid('You must provide exactly 2 of the following:'
                          ' start, end, duration')
    return conf


UPDATE_SCHEMA = vol.Any(vol.Schema({
    vol.Required(CONF_AT): cv.time,
}), vol.All(vol.Schema({
    vol.Optional(CONF_HOURS): vol.Any(vol.Coerce(int), vol.Coerce(str)),
    vol.Optional(CONF_MINUTES): vol.Any(vol.Coerce(int), vol.Coerce(str)),
    vol.Optional(CONF_SECONDS): vol.Any(vol.Coerce(int), vol.Coerce(str)),
}), cv.has_at_least_one_key(CONF_HOURS, CONF_MINUTES, CONF_SECONDS)))

PLATFORM_SCHEMA = vol.All(PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_TYPE): vol.In([TYPE_AVG, TYPE_LOW, TYPE_PEAK,
                                     TYPE_RANGE]),
    vol.Required(CONF_TARGET_ENTITY): cv.entity_id,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_START): cv.template,
    vol.Optional(CONF_END): cv.template,
    vol.Optional(CONF_DURATION): cv.time_period,
    vol.Optional(CONF_UPDATE): UPDATE_SCHEMA,
}), exactly_two_period_keys)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the history sensors."""
    name = config[CONF_NAME]
    entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, name, hass=hass)
    sensor_type = config[CONF_TYPE]
    target_entity = config[CONF_TARGET_ENTITY]
    unit = config.get(CONF_UNIT_OF_MEASUREMENT)
    start = config.get(CONF_START)
    end = config.get(CONF_END)
    duration = config.get(CONF_DURATION)
    update = config.get(CONF_UPDATE)
    _LOGGER.debug("Update %s", config)
    if update is not None and CONF_AT in update:
        at_time = update.get(CONF_AT)
        update = {
            CONF_HOURS: at_time.hour,
            CONF_MINUTES: at_time.minute,
            CONF_SECONDS: at_time.second,
            }
    for template in [start, end]:
        if template is not None:
            template.hass = hass
    async_add_entities([HistoryValuesSensor(name, entity_id, sensor_type,
                                            target_entity, unit, start, end,
                                            duration, update)])


class HistoryValuesSensor(Entity):
    """HistoryValuesSensor class."""

    def __init__(self, name, entity_id, sensor_type, target_entity, unit,
                 start, end, duration, update):
        """Initialize the sensor."""
        self.entity_id = entity_id
        self._friendly_name = name
        self._type = sensor_type
        self._target_entity = target_entity
        self._unit_of_measurement = unit
        self._start = start
        self._end = end
        self._duration = duration
        self._update = update
        self._device_class = None
        self._period = (datetime.datetime.now(), datetime.datetime.now())
        self.value = STATE_UNKNOWN

    async def async_added_to_hass(self):
        """Set up first update and update schedule."""
        async def init_sensor(event):
            """Initialize basic sensor settings."""
            _LOGGER.debug("Received event: %s", event)
            if (event.data[ATTR_ENTITY_ID] != self._target_entity
                    or event.data[ATTR_NEW_STATE] is None
                    or event.data[ATTR_NEW_STATE].state == STATE_UNKNOWN):
                return
            remove_listener()
            comp = event.data[ATTR_NEW_STATE]
            if comp is not None:
                self._device_class = comp.attributes.get('device_class')
                if self._unit_of_measurement is None:
                    self._unit_of_measurement = comp.attributes.get(
                        CONF_UNIT_OF_MEASUREMENT)
            await self.async_update()
        remove_listener = self.hass.bus.async_listen(EVENT_STATE_CHANGED,
                                                     init_sensor)
        comp = self.hass.states.get(self._target_entity)
        if comp is not None:
            self.hass.bus.async_fire(EVENT_STATE_CHANGED, {
                ATTR_ENTITY_ID: self._target_entity,
                ATTR_NEW_STATE: comp,
            })

        if self._update is not None:
            _LOGGER.debug("Registering updates: %s", self._update)

            @callback
            def trigger_update(now):
                """Trigger an update of the sensor."""
                self.hass.async_create_task(self.async_update())
            async_track_time_change(self.hass, trigger_update,
                                    hour=self._update.get(CONF_HOURS),
                                    minute=self._update.get(CONF_MINUTES),
                                    second=self._update.get(CONF_SECONDS))

    async def async_update(self):
        """Update the sensor."""
        _LOGGER.debug("Updating %s", self.entity_id)
        # Get previous values of start and end
        p_start, p_end = self._period

        # Parse templates
        await self.update_period()
        start, end = self._period

        # Convert times to UTC
        start = dt_util.as_utc(start)
        end = dt_util.as_utc(end)
        p_start = dt_util.as_utc(p_start)
        p_end = dt_util.as_utc(p_end)
        now = datetime.datetime.now(datetime.timezone.utc)

        # Compute integer timestamps
        start_timestamp = math.floor(dt_util.as_timestamp(start))
        end_timestamp = math.floor(dt_util.as_timestamp(end))
        p_start_timestamp = math.floor(dt_util.as_timestamp(p_start))
        p_end_timestamp = math.floor(dt_util.as_timestamp(p_end))
        now_timestamp = math.floor(dt_util.as_timestamp(now))

        # If period has not changed and current time after the period end...
        if (start_timestamp == p_start_timestamp
                and end_timestamp == p_end_timestamp
                and end_timestamp <= now_timestamp):
            # Don't compute anything as the value cannot have changed
            _LOGGER.debug("Update not necessary.")
            return

        # Get history between start and end
        history_states = await self.hass.async_add_job(
            history.state_changes_during_period, self.hass, start, end,
            str(self._target_entity))
        history_list = history_states.get(self._target_entity)
        if history_list is None:
            self.value = STATE_UNKNOWN
            return

        def is_castable_to_float(str):
            """Return True if @str is castable to float."""
            try:
                float(str)
            except (TypeError, ValueError):
                _LOGGER.warning("%s: Not a numeric value: %s",
                                self.entity_id, str)
                return False
            return True

        history_list = [state for state in history_list
                        if is_castable_to_float(state.state)]

        if self._type in [TYPE_LOW, TYPE_PEAK, TYPE_RANGE]:
            value = self.get_min_max_range(history_list)[self._type]
        if self._type == TYPE_AVG:
            value = self.get_average(history_list, end, now)
        if value is not None:
            self.value = value

        self.async_schedule_update_ha_state()

    @property
    def device_class(self):
        """Return the device_class of the sensor."""
        return self._device_class

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._friendly_name

    @property
    def should_poll(self):
        """Return False, we schedule our own updates."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.value

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the sensor."""
        return self._unit_of_measurement

    @callback
    def get_average(self, state_list, end, now):
        """Calculate and return the time-weighted average of @state_list."""
        if state_list is None:
            return
        total_value = 0
        total_period = datetime.timedelta(seconds=0)
        last_idx = len(state_list) - 1
        for state in state_list:
            next_updated = state_list.index(state) + 1
            if next_updated > last_idx:
                if end > now:
                    next_time = now
                else:
                    next_time = end
            else:
                next_time = state_list[next_updated].last_changed
            state_period = next_time - state.last_changed
            total_period += state_period
            total_value += float(state.state) * state_period.total_seconds()
        if total_period.total_seconds() == 0:
            return None

        def get_precision(float_num, max_prec=10):
            """Return the precision of @float up to @max."""
            count = 0
            orig_num = float_num
            while int(float_num) != float_num and count < max_prec:
                count += 1
                float_num = orig_num * 10**count
            return count

        precision = max([
            get_precision(float(state.state)) for state in state_list])
        formatstr = '{:.' + str(precision) + 'f}'
        return formatstr.format(total_value / total_period.total_seconds())

    @callback
    def get_min_max_range(self, state_list):
        """Return a dict with highest, lowest and range of @state_list."""
        if state_list is None:
            return
        high = low = None
        for state in state_list:
            new = Decimal(state.state)
            if high is None or new > high:
                high = new
            if low is None or new < low:
                low = new
        if high is None:  # low will be None as well
            val_range = None
        else:
            val_range = high - low
        return {
            TYPE_LOW: low,
            TYPE_PEAK: high,
            TYPE_RANGE: val_range,
            }

    async def update_period(self):
        """Parse the templates and store a datetime tuple in _period."""
        start = None
        end = None

        # Parse start
        if self._start is not None:
            try:
                start_rendered = self._start.async_render()
            except (TemplateError, TypeError) as ex:
                self.handle_template_exception(ex, 'start')
                return
            start = dt_util.parse_datetime(start_rendered)
            if start is None:
                try:
                    start = dt_util.as_local(dt_util.utc_from_timestamp(
                        math.floor(float(start_rendered))))
                except ValueError:
                    _LOGGER.error("Parsing error: start must be a datetime"
                                  "or a timestamp")
                    return

        # Parse end
        if self._end is not None:
            try:
                end_rendered = self._end.async_render()
            except (TemplateError, TypeError) as ex:
                self.handle_template_exception(ex, 'end')
                return
            end = dt_util.parse_datetime(end_rendered)
            if end is None:
                try:
                    end = dt_util.as_local(dt_util.utc_from_timestamp(
                        math.floor(float(end_rendered))))
                except ValueError:
                    _LOGGER.error("Parsing error: end must be a datetime "
                                  "or a timestamp")
                    return

        # Calculate start or end using the duration
        if start is None:
            start = end - self._duration
        if end is None:
            end = start + self._duration

        self._period = start, end

    @callback
    @staticmethod
    def handle_template_exception(ex, field):
        """Log an error nicely if the template cannot be interpreted."""
        if ex.args and ex.args[0].startswith(
                "UndefinedError: 'None' has no attribute"):
            # Common during HA startup - so just a warning
            _LOGGER.warning(ex)
            return
        _LOGGER.error("Error parsing template for field %s", field)
        _LOGGER.error(ex)
