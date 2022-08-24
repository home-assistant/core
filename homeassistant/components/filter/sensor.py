"""Allows the creation of a sensor that filters state property."""
from __future__ import annotations

from collections import Counter, deque
from copy import copy
from datetime import datetime, timedelta
from functools import partial
import logging
from numbers import Number
import statistics
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.components.recorder import get_instance, history
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DEVICE_CLASSES as SENSOR_DEVICE_CLASSES,
    DOMAIN as SENSOR_DOMAIN,
    PLATFORM_SCHEMA,
    STATE_CLASSES as SENSOR_STATE_CLASSES,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, State, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.decorator import Registry
import homeassistant.util.dt as dt_util

from . import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

FILTER_NAME_RANGE = "range"
FILTER_NAME_LOWPASS = "lowpass"
FILTER_NAME_OUTLIER = "outlier"
FILTER_NAME_THROTTLE = "throttle"
FILTER_NAME_TIME_THROTTLE = "time_throttle"
FILTER_NAME_TIME_SMA = "time_simple_moving_average"
FILTERS: Registry[str, type[Filter]] = Registry()

CONF_FILTERS = "filters"
CONF_FILTER_NAME = "filter"
CONF_FILTER_WINDOW_SIZE = "window_size"
CONF_FILTER_PRECISION = "precision"
CONF_FILTER_RADIUS = "radius"
CONF_FILTER_TIME_CONSTANT = "time_constant"
CONF_FILTER_LOWER_BOUND = "lower_bound"
CONF_FILTER_UPPER_BOUND = "upper_bound"
CONF_TIME_SMA_TYPE = "type"

TIME_SMA_LAST = "last"

WINDOW_SIZE_UNIT_NUMBER_EVENTS = 1
WINDOW_SIZE_UNIT_TIME = 2

DEFAULT_WINDOW_SIZE = 1
DEFAULT_PRECISION = 2
DEFAULT_FILTER_RADIUS = 2.0
DEFAULT_FILTER_TIME_CONSTANT = 10

NAME_TEMPLATE = "{} filter"
ICON = "mdi:chart-line-variant"

FILTER_SCHEMA = vol.Schema(
    {vol.Optional(CONF_FILTER_PRECISION, default=DEFAULT_PRECISION): vol.Coerce(int)}
)

FILTER_OUTLIER_SCHEMA = FILTER_SCHEMA.extend(
    {
        vol.Required(CONF_FILTER_NAME): FILTER_NAME_OUTLIER,
        vol.Optional(CONF_FILTER_WINDOW_SIZE, default=DEFAULT_WINDOW_SIZE): vol.Coerce(
            int
        ),
        vol.Optional(CONF_FILTER_RADIUS, default=DEFAULT_FILTER_RADIUS): vol.Coerce(
            float
        ),
    }
)

FILTER_LOWPASS_SCHEMA = FILTER_SCHEMA.extend(
    {
        vol.Required(CONF_FILTER_NAME): FILTER_NAME_LOWPASS,
        vol.Optional(CONF_FILTER_WINDOW_SIZE, default=DEFAULT_WINDOW_SIZE): vol.Coerce(
            int
        ),
        vol.Optional(
            CONF_FILTER_TIME_CONSTANT, default=DEFAULT_FILTER_TIME_CONSTANT
        ): vol.Coerce(int),
    }
)

FILTER_RANGE_SCHEMA = FILTER_SCHEMA.extend(
    {
        vol.Required(CONF_FILTER_NAME): FILTER_NAME_RANGE,
        vol.Optional(CONF_FILTER_LOWER_BOUND): vol.Coerce(float),
        vol.Optional(CONF_FILTER_UPPER_BOUND): vol.Coerce(float),
    }
)

FILTER_TIME_SMA_SCHEMA = FILTER_SCHEMA.extend(
    {
        vol.Required(CONF_FILTER_NAME): FILTER_NAME_TIME_SMA,
        vol.Optional(CONF_TIME_SMA_TYPE, default=TIME_SMA_LAST): vol.In(
            [TIME_SMA_LAST]
        ),
        vol.Required(CONF_FILTER_WINDOW_SIZE): vol.All(
            cv.time_period, cv.positive_timedelta
        ),
    }
)

FILTER_THROTTLE_SCHEMA = FILTER_SCHEMA.extend(
    {
        vol.Required(CONF_FILTER_NAME): FILTER_NAME_THROTTLE,
        vol.Optional(CONF_FILTER_WINDOW_SIZE, default=DEFAULT_WINDOW_SIZE): vol.Coerce(
            int
        ),
    }
)

FILTER_TIME_THROTTLE_SCHEMA = FILTER_SCHEMA.extend(
    {
        vol.Required(CONF_FILTER_NAME): FILTER_NAME_TIME_THROTTLE,
        vol.Required(CONF_FILTER_WINDOW_SIZE): vol.All(
            cv.time_period, cv.positive_timedelta
        ),
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): vol.Any(
            cv.entity_domain(SENSOR_DOMAIN),
            cv.entity_domain(BINARY_SENSOR_DOMAIN),
            cv.entity_domain(INPUT_NUMBER_DOMAIN),
        ),
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Required(CONF_FILTERS): vol.All(
            cv.ensure_list,
            [
                vol.Any(
                    FILTER_OUTLIER_SCHEMA,
                    FILTER_LOWPASS_SCHEMA,
                    FILTER_TIME_SMA_SCHEMA,
                    FILTER_THROTTLE_SCHEMA,
                    FILTER_TIME_THROTTLE_SCHEMA,
                    FILTER_RANGE_SCHEMA,
                )
            ],
        ),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template sensors."""

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    name: str | None = config.get(CONF_NAME)
    unique_id: str | None = config.get(CONF_UNIQUE_ID)
    entity_id: str = config[CONF_ENTITY_ID]

    filter_configs: list[dict[str, Any]] = config[CONF_FILTERS]
    filters = [
        FILTERS[_filter.pop(CONF_FILTER_NAME)](entity=entity_id, **_filter)
        for _filter in filter_configs
    ]

    async_add_entities([SensorFilter(name, unique_id, entity_id, filters)])


class SensorFilter(SensorEntity):
    """Representation of a Filter Sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        name: str | None,
        unique_id: str | None,
        entity_id: str,
        filters: list[Filter],
    ) -> None:
        """Initialize the sensor."""
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._entity = entity_id
        self._attr_native_unit_of_measurement = None
        self._state: str | None = None
        self._filters = filters
        self._attr_icon = None
        self._attr_device_class = None
        self._attr_state_class = None
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: entity_id}

    @callback
    def _update_filter_sensor_state_event(self, event: Event) -> None:
        """Handle device state changes."""
        _LOGGER.debug("Update filter on event: %s", event)
        self._update_filter_sensor_state(event.data.get("new_state"))

    @callback
    def _update_filter_sensor_state(
        self, new_state: State | None, update_ha: bool = True
    ) -> None:
        """Process device state changes."""
        if new_state is None:
            _LOGGER.warning(
                "While updating filter %s, the new_state is None", self.name
            )
            self._state = None
            self.async_write_ha_state()
            return

        if new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._state = new_state.state
            self.async_write_ha_state()
            return

        temp_state = new_state

        try:
            for filt in self._filters:
                filtered_state = filt.filter_state(copy(temp_state))
                _LOGGER.debug(
                    "%s(%s=%s) -> %s",
                    filt.name,
                    self._entity,
                    temp_state.state,
                    "skip" if filt.skip_processing else filtered_state.state,
                )
                if filt.skip_processing:
                    return
                temp_state = filtered_state
        except ValueError:
            _LOGGER.error(
                "Could not convert state: %s (%s) to number",
                new_state.state,
                type(new_state.state),
            )
            return

        self._state = temp_state.state

        if self._attr_icon is None:
            self._attr_icon = new_state.attributes.get(ATTR_ICON, ICON)

        if (
            self._attr_device_class is None
            and new_state.attributes.get(ATTR_DEVICE_CLASS) in SENSOR_DEVICE_CLASSES
        ):
            self._attr_device_class = new_state.attributes.get(ATTR_DEVICE_CLASS)

        if (
            self._attr_state_class is None
            and new_state.attributes.get(ATTR_STATE_CLASS) in SENSOR_STATE_CLASSES
        ):
            self._attr_state_class = new_state.attributes.get(ATTR_STATE_CLASS)

        if self._attr_native_unit_of_measurement is None:
            self._attr_native_unit_of_measurement = new_state.attributes.get(
                ATTR_UNIT_OF_MEASUREMENT
            )

        if update_ha:
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        if "recorder" in self.hass.config.components:
            history_list = []
            largest_window_items = 0
            largest_window_time = timedelta(0)

            # Determine the largest window_size by type
            for filt in self._filters:
                if (
                    filt.window_unit == WINDOW_SIZE_UNIT_NUMBER_EVENTS
                    and largest_window_items < filt.window_size
                ):
                    largest_window_items = filt.window_size
                elif (
                    filt.window_unit == WINDOW_SIZE_UNIT_TIME
                    and largest_window_time < filt.window_size
                ):
                    largest_window_time = filt.window_size

            # Retrieve the largest window_size of each type
            if largest_window_items > 0:
                filter_history = await get_instance(self.hass).async_add_executor_job(
                    partial(
                        history.get_last_state_changes,
                        self.hass,
                        largest_window_items,
                        entity_id=self._entity,
                    )
                )
                if self._entity in filter_history:
                    history_list.extend(filter_history[self._entity])
            if largest_window_time > timedelta(seconds=0):
                start = dt_util.utcnow() - largest_window_time
                filter_history = await get_instance(self.hass).async_add_executor_job(
                    partial(
                        history.state_changes_during_period,
                        self.hass,
                        start,
                        entity_id=self._entity,
                    )
                )
                if self._entity in filter_history:
                    history_list.extend(
                        [
                            state
                            for state in filter_history[self._entity]
                            if state not in history_list
                        ]
                    )

            # Sort the window states
            history_list = sorted(history_list, key=lambda s: s.last_updated)
            _LOGGER.debug(
                "Loading from history: %s",
                [(s.state, s.last_updated) for s in history_list],
            )

            # Replay history through the filter chain
            for state in history_list:
                if state.state not in [STATE_UNKNOWN, STATE_UNAVAILABLE, None]:
                    self._update_filter_sensor_state(state, False)

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._entity], self._update_filter_sensor_state_event
            )
        )

    @property
    def native_value(self) -> datetime | str | None:
        """Return the state of the sensor."""
        if self._state is not None and self.device_class == SensorDeviceClass.TIMESTAMP:
            return datetime.fromisoformat(self._state)

        return self._state


class FilterState:
    """State abstraction for filter usage."""

    def __init__(self, state):
        """Initialize with HA State object."""
        self.timestamp = state.last_updated
        try:
            self.state = float(state.state)
        except ValueError:
            self.state = state.state

    def set_precision(self, precision):
        """Set precision of Number based states."""
        if isinstance(self.state, Number):
            value = round(float(self.state), precision)
            self.state = int(value) if precision == 0 else value

    def __str__(self):
        """Return state as the string representation of FilterState."""
        return str(self.state)

    def __repr__(self):
        """Return timestamp and state as the representation of FilterState."""
        return f"{self.timestamp} : {self.state}"


class Filter:
    """Filter skeleton."""

    def __init__(
        self,
        name,
        window_size: int = 1,
        precision: int | None = None,
        entity: str | None = None,
    ):
        """Initialize common attributes.

        :param window_size: size of the sliding window that holds previous values
        :param precision: round filtered value to precision value
        :param entity: used for debugging only
        """
        if isinstance(window_size, int):
            self.states: deque = deque(maxlen=window_size)
            self.window_unit = WINDOW_SIZE_UNIT_NUMBER_EVENTS
        else:
            self.states = deque(maxlen=0)
            self.window_unit = WINDOW_SIZE_UNIT_TIME
        self.precision = precision
        self._name = name
        self._entity = entity
        self._skip_processing = False
        self._window_size = window_size
        self._store_raw = False
        self._only_numbers = True

    @property
    def window_size(self):
        """Return window size."""
        return self._window_size

    @property
    def name(self):
        """Return filter name."""
        return self._name

    @property
    def skip_processing(self):
        """Return whether the current filter_state should be skipped."""
        return self._skip_processing

    def _filter_state(self, new_state):
        """Implement filter."""
        raise NotImplementedError()

    def filter_state(self, new_state):
        """Implement a common interface for filters."""
        fstate = FilterState(new_state)
        if self._only_numbers and not isinstance(fstate.state, Number):
            raise ValueError(f"State <{fstate.state}> is not a Number")

        filtered = self._filter_state(fstate)
        filtered.set_precision(self.precision)
        if self._store_raw:
            self.states.append(copy(FilterState(new_state)))
        else:
            self.states.append(copy(filtered))
        new_state.state = filtered.state
        return new_state


@FILTERS.register(FILTER_NAME_RANGE)
class RangeFilter(Filter, SensorEntity):
    """Range filter.

    Determines if new state is in the range of upper_bound and lower_bound.
    If not inside, lower or upper bound is returned instead.
    """

    def __init__(
        self,
        entity,
        precision: int | None = DEFAULT_PRECISION,
        lower_bound: float | None = None,
        upper_bound: float | None = None,
    ):
        """Initialize Filter.

        :param upper_bound: band upper bound
        :param lower_bound: band lower bound
        """
        super().__init__(FILTER_NAME_RANGE, precision=precision, entity=entity)
        self._lower_bound = lower_bound
        self._upper_bound = upper_bound
        self._stats_internal: Counter = Counter()

    def _filter_state(self, new_state):
        """Implement the range filter."""

        if self._upper_bound is not None and new_state.state > self._upper_bound:

            self._stats_internal["erasures_up"] += 1

            _LOGGER.debug(
                "Upper outlier nr. %s in %s: %s",
                self._stats_internal["erasures_up"],
                self._entity,
                new_state,
            )
            new_state.state = self._upper_bound

        elif self._lower_bound is not None and new_state.state < self._lower_bound:

            self._stats_internal["erasures_low"] += 1

            _LOGGER.debug(
                "Lower outlier nr. %s in %s: %s",
                self._stats_internal["erasures_low"],
                self._entity,
                new_state,
            )
            new_state.state = self._lower_bound

        return new_state


@FILTERS.register(FILTER_NAME_OUTLIER)
class OutlierFilter(Filter, SensorEntity):
    """BASIC outlier filter.

    Determines if new state is in a band around the median.
    """

    def __init__(self, window_size, precision, entity, radius: float):
        """Initialize Filter.

        :param radius: band radius
        """
        super().__init__(FILTER_NAME_OUTLIER, window_size, precision, entity)
        self._radius = radius
        self._stats_internal: Counter = Counter()
        self._store_raw = True

    def _filter_state(self, new_state):
        """Implement the outlier filter."""

        median = statistics.median([s.state for s in self.states]) if self.states else 0
        if (
            len(self.states) == self.states.maxlen
            and abs(new_state.state - median) > self._radius
        ):

            self._stats_internal["erasures"] += 1

            _LOGGER.debug(
                "Outlier nr. %s in %s: %s",
                self._stats_internal["erasures"],
                self._entity,
                new_state,
            )
            new_state.state = median
        return new_state


@FILTERS.register(FILTER_NAME_LOWPASS)
class LowPassFilter(Filter, SensorEntity):
    """BASIC Low Pass Filter."""

    def __init__(self, window_size, precision, entity, time_constant: int):
        """Initialize Filter."""
        super().__init__(FILTER_NAME_LOWPASS, window_size, precision, entity)
        self._time_constant = time_constant

    def _filter_state(self, new_state):
        """Implement the low pass filter."""

        if not self.states:
            return new_state

        new_weight = 1.0 / self._time_constant
        prev_weight = 1.0 - new_weight
        new_state.state = (
            prev_weight * self.states[-1].state + new_weight * new_state.state
        )

        return new_state


@FILTERS.register(FILTER_NAME_TIME_SMA)
class TimeSMAFilter(Filter, SensorEntity):
    """Simple Moving Average (SMA) Filter.

    The window_size is determined by time, and SMA is time weighted.
    """

    def __init__(
        self, window_size, precision, entity, type
    ):  # pylint: disable=redefined-builtin
        """Initialize Filter.

        :param type: type of algorithm used to connect discrete values
        """
        super().__init__(FILTER_NAME_TIME_SMA, window_size, precision, entity)
        self._time_window = window_size
        self.last_leak = None
        self.queue = deque()

    def _leak(self, left_boundary):
        """Remove timeouted elements."""
        while self.queue:
            if self.queue[0].timestamp + self._time_window <= left_boundary:
                self.last_leak = self.queue.popleft()
            else:
                return

    def _filter_state(self, new_state):
        """Implement the Simple Moving Average filter."""

        self._leak(new_state.timestamp)
        self.queue.append(copy(new_state))

        moving_sum = 0
        start = new_state.timestamp - self._time_window
        prev_state = self.last_leak or self.queue[0]
        for state in self.queue:
            moving_sum += (state.timestamp - start).total_seconds() * prev_state.state
            start = state.timestamp
            prev_state = state

        new_state.state = moving_sum / self._time_window.total_seconds()

        return new_state


@FILTERS.register(FILTER_NAME_THROTTLE)
class ThrottleFilter(Filter, SensorEntity):
    """Throttle Filter.

    One sample per window.
    """

    def __init__(self, window_size, precision, entity):
        """Initialize Filter."""
        super().__init__(FILTER_NAME_THROTTLE, window_size, precision, entity)
        self._only_numbers = False

    def _filter_state(self, new_state):
        """Implement the throttle filter."""
        if not self.states or len(self.states) == self.states.maxlen:
            self.states.clear()
            self._skip_processing = False
        else:
            self._skip_processing = True

        return new_state


@FILTERS.register(FILTER_NAME_TIME_THROTTLE)
class TimeThrottleFilter(Filter, SensorEntity):
    """Time Throttle Filter.

    One sample per time period.
    """

    def __init__(self, window_size, precision, entity):
        """Initialize Filter."""
        super().__init__(FILTER_NAME_TIME_THROTTLE, window_size, precision, entity)
        self._time_window = window_size
        self._last_emitted_at = None
        self._only_numbers = False

    def _filter_state(self, new_state):
        """Implement the filter."""
        window_start = new_state.timestamp - self._time_window
        if not self._last_emitted_at or self._last_emitted_at <= window_start:
            self._last_emitted_at = new_state.timestamp
            self._skip_processing = False
        else:
            self._skip_processing = True

        return new_state
