"""Component to make instant statistics about your history."""
from __future__ import annotations

import datetime
import logging
import math

import voluptuous as vol

from homeassistant.components.recorder import get_instance, history
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_STATE,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_START,
    PERCENTAGE,
    TIME_HOURS,
)
from homeassistant.core import CoreState, Event, HomeAssistant, State, callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from . import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CONF_START = "start"
CONF_END = "end"
CONF_DURATION = "duration"
CONF_PERIOD_KEYS = [CONF_START, CONF_END, CONF_DURATION]

CONF_TYPE_TIME = "time"
CONF_TYPE_RATIO = "ratio"
CONF_TYPE_COUNT = "count"
CONF_TYPE_KEYS = [CONF_TYPE_TIME, CONF_TYPE_RATIO, CONF_TYPE_COUNT]

DEFAULT_NAME = "unnamed statistics"
UNITS = {
    CONF_TYPE_TIME: TIME_HOURS,
    CONF_TYPE_RATIO: PERCENTAGE,
    CONF_TYPE_COUNT: "",
}
ICON = "mdi:chart-line"

ATTR_VALUE = "value"


def exactly_two_period_keys(conf):
    """Ensure exactly 2 of CONF_PERIOD_KEYS are provided."""
    if sum(param in conf for param in CONF_PERIOD_KEYS) != 2:
        raise vol.Invalid(
            "You must provide exactly 2 of the following: start, end, duration"
        )
    return conf


PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_ENTITY_ID): cv.entity_id,
            vol.Required(CONF_STATE): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_START): cv.template,
            vol.Optional(CONF_END): cv.template,
            vol.Optional(CONF_DURATION): cv.time_period,
            vol.Optional(CONF_TYPE, default=CONF_TYPE_TIME): vol.In(CONF_TYPE_KEYS),
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        }
    ),
    exactly_two_period_keys,
)


# noinspection PyUnusedLocal
async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the History Stats sensor."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    entity_id = config.get(CONF_ENTITY_ID)
    entity_states = config.get(CONF_STATE)
    start = config.get(CONF_START)
    end = config.get(CONF_END)
    duration = config.get(CONF_DURATION)
    sensor_type = config.get(CONF_TYPE)
    name = config.get(CONF_NAME)

    for template in (start, end):
        if template is not None:
            template.hass = hass

    async_add_entities(
        [
            HistoryStatsSensor(
                hass, entity_id, entity_states, start, end, duration, sensor_type, name
            )
        ]
    )


class HistoryStatsSensor(SensorEntity):
    """Representation of a HistoryStats sensor."""

    def __init__(
        self, hass, entity_id, entity_states, start, end, duration, sensor_type, name
    ):
        """Initialize the HistoryStats sensor."""
        self._entity_id = entity_id
        self._entity_states = entity_states
        self._duration = duration
        self._start = start
        self._end = end
        self._type = sensor_type
        self._name = name
        self._unit_of_measurement = UNITS[sensor_type]

        self._period = (datetime.datetime.min, datetime.datetime.min)
        self.value = None
        self.count = None
        self._history_current_period: list[State] = []
        self._previous_run_before_start = False

    @callback
    def _async_start_refresh(self, *_) -> None:
        """Register state tracking."""
        self.async_schedule_update_ha_state(True)
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._entity_id], self._async_update_from_event
            )
        )

    async def async_added_to_hass(self):
        """Create listeners when the entity is added."""
        if self.hass.state == CoreState.running:
            self._async_start_refresh()
            return
        # Delay first refresh to keep startup fast
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, self._async_start_refresh
        )

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        await self._async_update(None)

    async def _async_update_from_event(self, event: Event) -> None:
        """Do an update and write the state if its changed."""
        await self._async_update(event)
        self.async_write_ha_state()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.value is None or self.count is None:
            return None

        if self._type == CONF_TYPE_TIME:
            return round(self.value, 2)

        if self._type == CONF_TYPE_RATIO:
            return HistoryStatsHelper.pretty_ratio(self.value, self._period)

        if self._type == CONF_TYPE_COUNT:
            return self.count

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self.value is None:
            return {}

        hsh = HistoryStatsHelper
        return {ATTR_VALUE: hsh.pretty_duration(self.value)}

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    async def _async_update(self, event: Event | None) -> None:
        """Get the latest data and updates the states."""
        # Get previous values of start and end

        p_start, p_end = self._period

        # Parse templates
        self.update_period()
        start, end = self._period

        # Convert times to UTC
        start = dt_util.as_utc(start)
        end = dt_util.as_utc(end)
        p_start = dt_util.as_utc(p_start)
        p_end = dt_util.as_utc(p_end)
        now = datetime.datetime.now()

        # Compute integer timestamps
        start_timestamp = math.floor(dt_util.as_timestamp(start))
        end_timestamp = math.floor(dt_util.as_timestamp(end))
        p_start_timestamp = math.floor(dt_util.as_timestamp(p_start))
        p_end_timestamp = math.floor(dt_util.as_timestamp(p_end))
        now_timestamp = math.floor(dt_util.as_timestamp(now))

        if now_timestamp < start_timestamp:
            # History cannot tell the future
            self._history_current_period = []
            self._previous_run_before_start = True
        #
        # We avoid querying the database if the below did NOT happen:
        #
        # - The previous run happened before the start time
        # - The start time changed
        # - The period shrank in size
        # - The previous period ended before now
        #
        elif (
            not self._previous_run_before_start
            and start_timestamp == p_start_timestamp
            and (
                end_timestamp == p_end_timestamp
                or (
                    end_timestamp >= p_end_timestamp
                    and p_end_timestamp <= now_timestamp
                )
            )
        ):
            new_data = False
            if event and event.data["new_state"] is not None:
                new_state: State = event.data["new_state"]
                if start <= new_state.last_changed <= end:
                    self._history_current_period.append(new_state)
                    new_data = True
            if not new_data and end_timestamp < now_timestamp:
                # If period has not changed and current time after the period end...
                # Don't compute anything as the value cannot have changed
                return
        else:
            self._history_current_period = await get_instance(
                self.hass
            ).async_add_executor_job(
                self._update,
                start,
                end,
            )
            self._previous_run_before_start = False

        if not self._history_current_period:
            self.value = None
            self.count = None
            return

        self._async_compute_hours_and_changes(
            now_timestamp,
            start_timestamp,
            end_timestamp,
        )

    def _update(self, start: datetime.datetime, end: datetime.datetime) -> list[State]:
        """Update from the database."""
        # Get history between start and end
        return history.state_changes_during_period(
            self.hass,
            start,
            end,
            self._entity_id,
            include_start_time_state=True,
            no_attributes=True,
        ).get(self._entity_id, [])

    def _async_compute_hours_and_changes(
        self, now_timestamp: float, start_timestamp: float, end_timestamp: float
    ) -> None:
        """Compute the hours matched and changes from the history list and first state."""
        _LOGGER.debug(
            "%s: _async_compute_hours_and_changes: %s (%s)",
            self.entity_id,
            self._history_current_period,
            self._entity_states,
        )
        # state_changes_during_period is called with include_start_time_state=True
        # which is the default and always provides the state at the start
        # of the period
        last_state = (
            self._history_current_period
            and self._history_current_period[0].state in self._entity_states
        )
        last_time = start_timestamp
        elapsed = 0.0
        count = 0

        # Make calculations
        for item in self._history_current_period:
            current_state = item.state in self._entity_states
            current_time = item.last_changed.timestamp()

            if last_state:
                elapsed += current_time - last_time
            if current_state and not last_state:
                count += 1

            last_state = current_state
            last_time = current_time

        # Count time elapsed between last history state and end of measure
        if last_state:
            measure_end = min(end_timestamp, now_timestamp)
            elapsed += measure_end - last_time

        # Save value in hours
        self.value = elapsed / 3600

        # Save counter
        self.count = count

    def update_period(self):
        """Parse the templates and store a datetime tuple in _period."""
        start = None
        end = None

        # Parse start
        if self._start is not None:
            try:
                start_rendered = self._start.async_render()
            except (TemplateError, TypeError) as ex:
                HistoryStatsHelper.handle_template_exception(ex, "start")
                return
            if isinstance(start_rendered, str):
                start = dt_util.parse_datetime(start_rendered)
            if start is None:
                try:
                    start = dt_util.as_local(
                        dt_util.utc_from_timestamp(math.floor(float(start_rendered)))
                    )
                except ValueError:
                    _LOGGER.error(
                        "Parsing error: start must be a datetime or a timestamp"
                    )
                    return

        # Parse end
        if self._end is not None:
            try:
                end_rendered = self._end.async_render()
            except (TemplateError, TypeError) as ex:
                HistoryStatsHelper.handle_template_exception(ex, "end")
                return
            if isinstance(end_rendered, str):
                end = dt_util.parse_datetime(end_rendered)
            if end is None:
                try:
                    end = dt_util.as_local(
                        dt_util.utc_from_timestamp(math.floor(float(end_rendered)))
                    )
                except ValueError:
                    _LOGGER.error(
                        "Parsing error: end must be a datetime or a timestamp"
                    )
                    return

        # Calculate start or end using the duration
        if start is None:
            start = end - self._duration
        if end is None:
            end = start + self._duration

        self._period = start, end


class HistoryStatsHelper:
    """Static methods to make the HistoryStatsSensor code lighter."""

    @staticmethod
    def pretty_duration(hours):
        """Format a duration in days, hours, minutes, seconds."""
        seconds = int(3600 * hours)
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        if days > 0:
            return "%dd %dh %dm" % (days, hours, minutes)
        if hours > 0:
            return "%dh %dm" % (hours, minutes)
        return "%dm" % minutes

    @staticmethod
    def pretty_ratio(value, period):
        """Format the ratio of value / period duration."""
        if len(period) != 2 or period[0] == period[1]:
            return 0.0

        ratio = 100 * 3600 * value / (period[1] - period[0]).total_seconds()
        return round(ratio, 1)

    @staticmethod
    def handle_template_exception(ex, field):
        """Log an error nicely if the template cannot be interpreted."""
        if ex.args and ex.args[0].startswith("UndefinedError: 'None' has no attribute"):
            # Common during HA startup - so just a warning
            _LOGGER.warning(ex)
            return
        _LOGGER.error("Error parsing template for field %s", field, exc_info=ex)
