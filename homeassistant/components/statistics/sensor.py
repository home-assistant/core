"""Support for statistics for sensor values."""

from __future__ import annotations

from collections.abc import Callable
import contextlib
from datetime import datetime, timedelta
import logging
import math
import statistics
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.recorder import get_instance, history
from homeassistant.components.sensor import (
    DEVICE_CLASS_STATE_CLASSES,
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_UNIQUE_ID,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
    split_entity_id,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device import async_device_info_to_link_from_entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.util import dt as dt_util
from homeassistant.util.enum import try_parse_enum

from . import DOMAIN, PLATFORMS
from .state_buffer import BufferedState, StateBuffer, StateData

_LOGGER = logging.getLogger(__name__)

# Stats for attributes only
STAT_AGE_COVERAGE_RATIO = "age_coverage_ratio"
STAT_BUFFER_USAGE_RATIO = "buffer_usage_ratio"
STAT_SOURCE_VALUE_VALID = "source_value_valid"

# All sensor statistics
STAT_AVERAGE_LINEAR = "average_linear"
STAT_AVERAGE_STEP = "average_step"
STAT_AVERAGE_TIMELESS = "average_timeless"
STAT_CHANGE = "change"
STAT_CHANGE_SAMPLE = "change_sample"
STAT_CHANGE_SECOND = "change_second"
STAT_COUNT = "count"
STAT_COUNT_BINARY_ON = "count_on"
STAT_COUNT_BINARY_OFF = "count_off"
STAT_DATETIME_NEWEST = "datetime_newest"
STAT_DATETIME_OLDEST = "datetime_oldest"
STAT_DATETIME_VALUE_MAX = "datetime_value_max"
STAT_DATETIME_VALUE_MIN = "datetime_value_min"
STAT_DISTANCE_95P = "distance_95_percent_of_values"
STAT_DISTANCE_99P = "distance_99_percent_of_values"
STAT_DISTANCE_ABSOLUTE = "distance_absolute"
STAT_MEAN = "mean"
STAT_MEAN_CIRCULAR = "mean_circular"
STAT_MEDIAN = "median"
STAT_NOISINESS = "noisiness"
STAT_PERCENTILE = "percentile"
STAT_STANDARD_DEVIATION = "standard_deviation"
STAT_SUM = "sum"
STAT_SUM_DIFFERENCES = "sum_differences"
STAT_SUM_DIFFERENCES_NONNEGATIVE = "sum_differences_nonnegative"
STAT_TOTAL = "total"
STAT_VALUE_MAX = "value_max"
STAT_VALUE_MIN = "value_min"
STAT_VARIANCE = "variance"

# Statistics supported by a sensor source (numeric)
STATS_NUMERIC_SUPPORT = {
    STAT_AVERAGE_LINEAR,
    STAT_AVERAGE_STEP,
    STAT_AVERAGE_TIMELESS,
    STAT_CHANGE_SAMPLE,
    STAT_CHANGE_SECOND,
    STAT_CHANGE,
    STAT_COUNT,
    STAT_DATETIME_NEWEST,
    STAT_DATETIME_OLDEST,
    STAT_DATETIME_VALUE_MAX,
    STAT_DATETIME_VALUE_MIN,
    STAT_DISTANCE_95P,
    STAT_DISTANCE_99P,
    STAT_DISTANCE_ABSOLUTE,
    STAT_MEAN,
    STAT_MEAN_CIRCULAR,
    STAT_MEDIAN,
    STAT_NOISINESS,
    STAT_PERCENTILE,
    STAT_STANDARD_DEVIATION,
    STAT_SUM,
    STAT_SUM_DIFFERENCES,
    STAT_SUM_DIFFERENCES_NONNEGATIVE,
    STAT_TOTAL,
    STAT_VALUE_MAX,
    STAT_VALUE_MIN,
    STAT_VARIANCE,
}

# Statistics supported by a binary_sensor source
STATS_BINARY_SUPPORT = {
    STAT_AVERAGE_STEP,
    STAT_AVERAGE_TIMELESS,
    STAT_COUNT,
    STAT_COUNT_BINARY_ON,
    STAT_COUNT_BINARY_OFF,
    STAT_DATETIME_NEWEST,
    STAT_DATETIME_OLDEST,
    STAT_MEAN,
}

STATS_NOT_A_NUMBER = {
    STAT_DATETIME_NEWEST,
    STAT_DATETIME_OLDEST,
    STAT_DATETIME_VALUE_MAX,
    STAT_DATETIME_VALUE_MIN,
}

STATS_DATETIME = {
    STAT_DATETIME_NEWEST,
    STAT_DATETIME_OLDEST,
    STAT_DATETIME_VALUE_MAX,
    STAT_DATETIME_VALUE_MIN,
}

# Statistics which retain the unit of the source entity
STATS_NUMERIC_RETAIN_UNIT = {
    STAT_AVERAGE_LINEAR,
    STAT_AVERAGE_STEP,
    STAT_AVERAGE_TIMELESS,
    STAT_CHANGE,
    STAT_DISTANCE_95P,
    STAT_DISTANCE_99P,
    STAT_DISTANCE_ABSOLUTE,
    STAT_MEAN,
    STAT_MEAN_CIRCULAR,
    STAT_MEDIAN,
    STAT_NOISINESS,
    STAT_PERCENTILE,
    STAT_STANDARD_DEVIATION,
    STAT_SUM,
    STAT_SUM_DIFFERENCES,
    STAT_SUM_DIFFERENCES_NONNEGATIVE,
    STAT_TOTAL,
    STAT_VALUE_MAX,
    STAT_VALUE_MIN,
}

# Statistics which produce percentage ratio from binary_sensor source entity
STATS_BINARY_PERCENTAGE = {
    STAT_AVERAGE_STEP,
    STAT_AVERAGE_TIMELESS,
    STAT_MEAN,
}

CONF_STATE_CHARACTERISTIC = "state_characteristic"
CONF_SAMPLES_MAX_BUFFER_SIZE = "sampling_size"
CONF_MAX_AGE = "max_age"
CONF_REFRESH_INTERVAL = "refresh_interval"
CONF_KEEP_LAST_SAMPLE = "keep_last_sample"
CONF_PRECISION = "precision"
CONF_PERCENTILE = "percentile"

DEFAULT_NAME = "Statistical characteristic"
DEFAULT_PRECISION = 2
ICON = "mdi:calculator"


def valid_state_characteristic_configuration(config: dict[str, Any]) -> dict[str, Any]:
    """Validate that the characteristic selected is valid for the source sensor type, throw if it isn't."""
    is_binary = split_entity_id(config[CONF_ENTITY_ID])[0] == BINARY_SENSOR_DOMAIN
    characteristic = cast(str, config[CONF_STATE_CHARACTERISTIC])
    if (is_binary and characteristic not in STATS_BINARY_SUPPORT) or (
        not is_binary and characteristic not in STATS_NUMERIC_SUPPORT
    ):
        raise vol.ValueInvalid(
            f"The configured characteristic '{characteristic}' is not supported "
            "for the configured source sensor"
        )
    return config


def valid_boundary_configuration(config: dict[str, Any]) -> dict[str, Any]:
    """Validate that max_age, sampling_size, or both are provided."""
    max_buffer = config.get(CONF_SAMPLES_MAX_BUFFER_SIZE)
    max_age = config.get(CONF_MAX_AGE)
    state_characteristic = config.get(CONF_STATE_CHARACTERISTIC)

    if max_buffer is None and max_age is None:
        raise vol.RequiredFieldInvalid(
            "The sensor configuration must provide 'max_age' and/or 'sampling_size'"
        )
    if (
        (max_buffer is not None)
        and (max_age is not None)
        and (state_characteristic in [STAT_AVERAGE_STEP, STAT_AVERAGE_LINEAR])
    ):
        _LOGGER.warning(
            "%s: You have specified a buffer size as well as a buffer age for a time based function. "
            "This may lead to some unexpected behaviour when values are constant over longer periods. "
            "The average is only computed between the first and last change that happened during the specified time frame. "
            "If you want a proper average over the full time frame, do not specify a buffer size",
            config.get(CONF_NAME),
        )
    return config


def valid_keep_last_sample(config: dict[str, Any]) -> dict[str, Any]:
    """Validate that if keep_last_sample is set, max_age must also be set."""

    if config.get(CONF_KEEP_LAST_SAMPLE) is True and config.get(CONF_MAX_AGE) is None:
        raise vol.RequiredFieldInvalid(
            "The sensor configuration must provide 'max_age' if 'keep_last_sample' is True"
        )
    return config


_PLATFORM_SCHEMA_BASE = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Required(CONF_STATE_CHARACTERISTIC): cv.string,
        vol.Optional(CONF_SAMPLES_MAX_BUFFER_SIZE): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Optional(CONF_MAX_AGE): cv.time_period,
        vol.Optional(CONF_REFRESH_INTERVAL): cv.time_period,
        vol.Optional(CONF_KEEP_LAST_SAMPLE, default=False): cv.boolean,
        vol.Optional(CONF_PRECISION, default=DEFAULT_PRECISION): vol.Coerce(int),
        vol.Optional(CONF_PERCENTILE, default=50): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=99)
        ),
    }
)
PLATFORM_SCHEMA = vol.All(
    _PLATFORM_SCHEMA_BASE,
    valid_state_characteristic_configuration,
    valid_boundary_configuration,
    valid_keep_last_sample,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Statistics sensor."""

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    async_add_entities(
        new_entities=[
            StatisticsSensor(
                hass=hass,
                source_entity_id=config[CONF_ENTITY_ID],
                name=config[CONF_NAME],
                unique_id=config.get(CONF_UNIQUE_ID),
                state_characteristic=config[CONF_STATE_CHARACTERISTIC],
                samples_max_buffer_size=config.get(CONF_SAMPLES_MAX_BUFFER_SIZE),
                samples_max_age=config.get(CONF_MAX_AGE),
                samples_keep_last=config[CONF_KEEP_LAST_SAMPLE],
                refresh_interval=config.get(CONF_REFRESH_INTERVAL),
                precision=config[CONF_PRECISION],
                percentile=config[CONF_PERCENTILE],
            )
        ],
        update_before_add=True,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Statistics sensor entry."""
    sampling_size = entry.options.get(CONF_SAMPLES_MAX_BUFFER_SIZE)
    if sampling_size:
        sampling_size = int(sampling_size)

    max_age = None
    if max_age_input := entry.options.get(CONF_MAX_AGE):
        max_age = timedelta(
            hours=max_age_input["hours"],
            minutes=max_age_input["minutes"],
            seconds=max_age_input["seconds"],
        )

    refresh = None
    if refresh_input := entry.options.get(CONF_REFRESH_INTERVAL):
        refresh = timedelta(
            hours=refresh_input["hours"],
            minutes=refresh_input["minutes"],
            seconds=refresh_input["seconds"],
        )

    async_add_entities(
        [
            StatisticsSensor(
                hass=hass,
                source_entity_id=entry.options[CONF_ENTITY_ID],
                name=entry.options[CONF_NAME],
                unique_id=entry.entry_id,
                state_characteristic=entry.options[CONF_STATE_CHARACTERISTIC],
                samples_max_buffer_size=sampling_size,
                samples_max_age=max_age,
                samples_keep_last=entry.options[CONF_KEEP_LAST_SAMPLE],
                refresh_interval=refresh,
                precision=int(entry.options[CONF_PRECISION]),
                percentile=int(entry.options[CONF_PERCENTILE]),
            )
        ],
        True,
    )


class StatisticsSensor(SensorEntity):
    """Representation of a Statistics sensor."""

    _attr_should_poll = False
    _attr_icon = ICON

    def __init__(
        self,
        hass: HomeAssistant,
        source_entity_id: str,
        name: str,
        unique_id: str | None,
        state_characteristic: str,
        samples_max_buffer_size: int | None,
        samples_max_age: timedelta | None,
        samples_keep_last: bool,
        refresh_interval: timedelta | None,
        precision: int,
        percentile: int,
    ) -> None:
        """Initialize the Statistics sensor."""
        self._attr_name: str = name
        self._attr_unique_id: str | None = unique_id
        self._source_entity_id: str = source_entity_id
        self._attr_device_info = async_device_info_to_link_from_entity(
            hass,
            source_entity_id,
        )
        self.is_binary: bool = (
            split_entity_id(self._source_entity_id)[0] == BINARY_SENSOR_DOMAIN
        )
        self._state_characteristic: str = state_characteristic
        self._samples_max_buffer_size: int | None = samples_max_buffer_size
        self._samples_max_age: timedelta | None = samples_max_age
        self.samples_keep_last: bool = samples_keep_last
        self._refresh_interval: timedelta | None = refresh_interval
        self._precision: int = precision
        self._percentile: int = percentile
        self._value: StateType | datetime = None
        self._unit_of_measurement: str | None = None
        self._available: bool = False
        self._state_buffer: StateBuffer = StateBuffer(
            samples_max_buffer_size, samples_max_age
        )

        self.attributes: dict[str, StateType] = {}

        self._state_characteristic_fn: Callable[[StateData], StateType | datetime] = (
            self._callable_characteristic_fn(self._state_characteristic)
        )

        self._update_listener: CALLBACK_TYPE | None = None

    @callback
    def _async_stats_sensor_state_listener(
        self,
        event: Event[EventStateChangedData],
    ) -> None:
        """Handle the sensor state changes."""
        if (new_state := event.data["new_state"]) is None:
            return
        self._add_state_to_queue(new_state)
        self._refresh()

    @callback
    def _async_stats_sensor_startup(self, _: HomeAssistant) -> None:
        """Add listener and get recorded state."""
        _LOGGER.debug("Startup for %s", self.entity_id)
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._source_entity_id],
                self._async_stats_sensor_state_listener,
            )
        )
        if "recorder" in self.hass.config.components:
            self.hass.async_create_task(self._initialize_from_database())

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_at_start(self.hass, self._async_stats_sensor_startup)
        )

    def _add_state_to_queue(self, new_state: State) -> None:
        """Add the state to the queue."""
        is_valid: bool | None
        value: float = 0.0

        if new_state.state == STATE_UNAVAILABLE:
            is_valid = None
        elif new_state.state in (STATE_UNKNOWN, None, ""):
            is_valid = False
        else:
            try:
                if self.is_binary:
                    assert new_state.state in ("on", "off")
                    if new_state.state == "on":
                        value = 1.0
                    else:
                        value = 0.0
                else:
                    value = float(new_state.state)
                is_valid = True
            except ValueError:
                is_valid = False
                _LOGGER.error(
                    "%s: parsing error. Expected number or binary state, but received '%s'",
                    self.entity_id,
                    new_state.state,
                )

        if (
            self._state_buffer.insert(
                BufferedState(new_state.last_updated, value, is_valid)
            )
            == 1
        ):
            # update the state only if the value is the newest value added to the buffer
            # historic values loaded from the database will not change the state
            self._available = new_state.state != STATE_UNAVAILABLE
        if is_valid:
            self._unit_of_measurement = self._derive_unit_of_measurement(new_state)

    def _derive_unit_of_measurement(self, new_state: State) -> str | None:
        base_unit: str | None = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        unit: str | None
        if self.is_binary and self._state_characteristic in STATS_BINARY_PERCENTAGE:
            unit = PERCENTAGE
        elif not base_unit:
            unit = None
        elif self._state_characteristic in STATS_NUMERIC_RETAIN_UNIT:
            unit = base_unit
        elif (
            self._state_characteristic in STATS_NOT_A_NUMBER
            or self._state_characteristic
            in (
                STAT_COUNT,
                STAT_COUNT_BINARY_ON,
                STAT_COUNT_BINARY_OFF,
            )
        ):
            unit = None
        elif self._state_characteristic == STAT_VARIANCE:
            unit = base_unit + "²"
        elif self._state_characteristic == STAT_CHANGE_SAMPLE:
            unit = base_unit + "/sample"
        elif self._state_characteristic == STAT_CHANGE_SECOND:
            unit = base_unit + "/s"
        return unit

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the class of this device."""
        if self._state_characteristic in STATS_DATETIME:
            return SensorDeviceClass.TIMESTAMP
        if self._state_characteristic in STATS_NUMERIC_RETAIN_UNIT:
            source_state = self.hass.states.get(self._source_entity_id)
            if source_state is None:
                return None
            source_device_class = source_state.attributes.get(ATTR_DEVICE_CLASS)
            if source_device_class is None:
                return None
            sensor_device_class = try_parse_enum(SensorDeviceClass, source_device_class)
            if sensor_device_class is None:
                return None
            sensor_state_classes = DEVICE_CLASS_STATE_CLASSES.get(
                sensor_device_class, set()
            )
            if SensorStateClass.MEASUREMENT not in sensor_state_classes:
                return None
            return sensor_device_class
        return None

    @property
    def state_class(self) -> SensorStateClass | None:
        """Return the state class of this entity."""
        if self._state_characteristic in STATS_NOT_A_NUMBER:
            return None
        return SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self._value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def available(self) -> bool:
        """Return the availability of the sensor linked to the source sensor."""
        return self._available

    @property
    def extra_state_attributes(self) -> dict[str, StateType] | None:
        """Return the state attributes of the sensor."""
        return {
            key: value for key, value in self.attributes.items() if value is not None
        }

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        self._refresh()

    def _async_get_next_refresh_timestamp(
        self, state_data: StateData
    ) -> datetime | None:
        """Find out when we need to refresh the data."""
        # The refresh is either triggered by an element expiring
        #  or by a specified refresh interval (whatever comes first)
        next_expiry: datetime | None = None
        refresh_time: datetime | None = None
        result: datetime | None = None

        if self._samples_max_age:
            next_expiry = self._state_buffer.next_expiry_timestamp(
                state_data.update_time
            )
            if next_expiry:
                next_expiry = next_expiry + self._samples_max_age
        if self._refresh_interval:
            refresh_time = state_data.update_time + self._refresh_interval

        if next_expiry is None:
            result = refresh_time
        elif refresh_time is None or refresh_time > next_expiry:
            result = next_expiry
        else:
            result = refresh_time
        return result

    def _refresh(self) -> None:
        """Purge old states, update the sensor and schedule the next update."""
        _LOGGER.debug("%s: updating statistics", self.entity_id)
        state_data: StateData = self._update_value()
        self._update_attributes(state_data)

        # If max_age is set, ensure to update again after the defined interval.
        # By basing updates off the timestamps of sampled data we avoid updating
        # when none of the observed entities change.
        if timestamp := self._async_get_next_refresh_timestamp(state_data):
            _LOGGER.debug(
                "%s: scheduling update at %s (%f s from now)",
                self.entity_id,
                timestamp,
                (timestamp - state_data.update_time).total_seconds(),
            )
            self._async_cancel_update_listener()
            self._update_listener = async_track_point_in_utc_time(
                self.hass, self._async_scheduled_update, timestamp
            )
        if self.entity_id is not None:
            self.async_write_ha_state()

    @callback
    def _async_cancel_update_listener(self) -> None:
        """Cancel the scheduled update listener."""
        if self._update_listener:
            self._update_listener()
            self._update_listener = None

    @callback
    def _async_scheduled_update(self, now: datetime) -> None:
        """Timer callback for sensor update."""
        _LOGGER.debug("%s: executing scheduled update", self.entity_id)
        self._async_cancel_update_listener()
        self._refresh()

    def _fetch_states_from_database(self) -> list[State]:
        """Fetch the states from the database. In principle this should also load the last value before the time interval for the time based functions. However, this would mean loading the complete history without time or number limit, which is maybe a little too much effort."""
        _LOGGER.debug("%s: initializing values from the database", self.entity_id)
        lower_entity_id = self._source_entity_id.lower()
        if self._samples_max_age is not None:
            start_date = (
                dt_util.utcnow() - self._samples_max_age - timedelta(microseconds=1)
            )
            _LOGGER.debug(
                "%s: retrieve records not older then %s",
                self.entity_id,
                start_date,
            )
        else:
            start_date = datetime.fromtimestamp(0, tz=dt_util.UTC)
            _LOGGER.debug("%s: retrieving all records", self.entity_id)
        return history.state_changes_during_period(
            self.hass,
            start_date,
            entity_id=lower_entity_id,
            descending=True,
            limit=self._samples_max_buffer_size,
            include_start_time_state=False,
        ).get(lower_entity_id, [])

    async def _initialize_from_database(self) -> None:
        """Initialize the list of states from the database.

        The query will get the list of states in DESCENDING order so that we
        can limit the result to self._sample_size.

        If MaxAge is provided then query will restrict to entries younger then
        current datetime - MaxAge.
        """
        if states := await get_instance(self.hass).async_add_executor_job(
            self._fetch_states_from_database
        ):
            for state in states:
                self._add_state_to_queue(state)

        self._refresh()
        _LOGGER.debug("%s: initializing from database completed", self.entity_id)

    def _update_attributes(self, state_data: StateData) -> None:
        """Calculate and update the various attributes."""
        self.attributes[STAT_SOURCE_VALUE_VALID] = state_data.is_valid

        if self._samples_max_buffer_size is not None:
            self.attributes[STAT_BUFFER_USAGE_RATIO] = round(
                len(state_data.values) / self._samples_max_buffer_size, 2
            )

        if self._samples_max_age is not None:
            if len(state_data.values) >= 1:
                ratio: float = (
                    state_data.update_time - state_data.timestamps[0]
                ).total_seconds() / self._samples_max_age.total_seconds()
                # since we are keeping one value that lies before the specified time interval
                # the ratio could become larger than 1 (100 percent)
                ratio = min(ratio, 1.0)
                self.attributes[STAT_AGE_COVERAGE_RATIO] = round(ratio, 2)
            else:
                self.attributes[STAT_AGE_COVERAGE_RATIO] = None

    def _update_value(self) -> StateData:
        """Front to call the right statistical characteristics functions.

        One of the _stat_*() functions is represented by self._state_characteristic_fn().
        """
        state_data: StateData

        state_data = self._state_buffer.states(dt_util.utcnow())
        if state_data.is_valid:
            value = self._state_characteristic_fn(state_data)
            if self._state_characteristic not in STATS_NOT_A_NUMBER:
                with contextlib.suppress(TypeError):
                    value = round(cast(float, value), self._precision)
                    if self._precision == 0:
                        value = int(value)
            self._value = value
        else:
            value = STATE_UNAVAILABLE
        return state_data

    def _callable_characteristic_fn(
        self, characteristic: str
    ) -> Callable[[StateData], StateType | datetime]:
        """Return the function callable of one characteristic function."""
        function: Callable[[StateData], StateType | datetime] = getattr(
            self,
            f"_stat_binary_{characteristic}"
            if self.is_binary
            else f"_stat_{characteristic}",
        )
        return function

    def _compute_area(
        self,
        function: str,
        value1: float,
        value2: float,
        timestamp1: datetime,
        timestamp2: datetime,
        update_time: datetime,
    ) -> tuple[float, float]:
        area: float = 0.0
        age1_secs: float = (update_time - timestamp1).total_seconds()
        age2_secs: float = (update_time - timestamp2).total_seconds()
        max_age_secs: float = cast(timedelta, self._samples_max_age).total_seconds()
        if max_age_secs < age1_secs:
            # the first value is outside of the time frame, we have to compute only the part of the area within the time frame
            if function == STAT_AVERAGE_LINEAR:
                value1 = value1 + (value2 - value1) * (age1_secs - max_age_secs) / (
                    age1_secs - age2_secs
                )
            age1_secs = max_age_secs
        width: float = age1_secs - age2_secs
        assert width >= 0
        if function == STAT_AVERAGE_STEP:
            area = value1 * width
        elif function == STAT_AVERAGE_LINEAR:
            area = 0.5 * (value1 + value2) * width
        else:
            _LOGGER.error("Unsupported function %s used for area computation", function)
        return width, area

    def _stat_time_based_average(
        self, function: str, state_data: StateData, binary: bool
    ) -> StateType:
        total_area: float = 0
        total_width: float = 0
        result: float | None = None

        number_values = len(state_data.values)
        if number_values == 1:
            # if the value didn't change within the specified interval, we use the one and only value
            result = state_data.values[0]
        elif number_values > 1:
            for i in range(1, len(state_data.values)):
                width, area = self._compute_area(
                    function,
                    state_data.values[i - 1],
                    state_data.values[i],
                    state_data.timestamps[i - 1],
                    state_data.timestamps[i],
                    state_data.update_time,
                )
                total_area += area
                total_width += width
            # now add the area after the last change
            width, area = self._compute_area(
                function,
                state_data.values[-1],
                state_data.values[-1],
                state_data.timestamps[-1],
                state_data.update_time,
                state_data.update_time,
            )
            total_area += area
            total_width += width
            result = total_area / total_width
        if binary and (result is not None):
            result = 100.0 * result
        return result

    # Statistics for numeric sensor

    def _stat_average_linear(self, state_data: StateData) -> StateType:
        return self._stat_time_based_average(STAT_AVERAGE_LINEAR, state_data, False)

    def _stat_average_step(self, state_data: StateData) -> StateType:
        return self._stat_time_based_average(STAT_AVERAGE_STEP, state_data, False)

    def _stat_average_timeless(self, state_data: StateData) -> StateType:
        return self._stat_mean(state_data)

    def _stat_change(self, state_data: StateData) -> StateType:
        if len(state_data.values) > 0:
            return state_data.values[-1] - state_data.values[0]
        return None

    def _stat_change_sample(self, state_data: StateData) -> StateType:
        if len(state_data.values) > 1:
            return (state_data.values[-1] - state_data.values[0]) / (
                len(state_data.values) - 1
            )
        return None

    def _stat_change_second(self, state_data: StateData) -> StateType:
        if len(state_data.values) > 1:
            age_range_seconds = (
                state_data.timestamps[-1] - state_data.timestamps[0]
            ).total_seconds()
            if age_range_seconds > 0:
                return (
                    state_data.values[-1] - state_data.values[0]
                ) / age_range_seconds
        return None

    def _stat_count(self, state_data: StateData) -> StateType:
        return len(state_data.values)

    def _stat_datetime_newest(self, state_data: StateData) -> datetime | None:
        if len(state_data.values) > 0:
            return state_data.timestamps[-1]
        return None

    def _stat_datetime_oldest(self, state_data: StateData) -> datetime | None:
        if len(state_data.values) > 0:
            return state_data.timestamps[0]
        return None

    def _stat_datetime_value_max(self, state_data: StateData) -> datetime | None:
        if len(state_data.values) > 0:
            return state_data.timestamps[
                state_data.values.index(max(state_data.values))
            ]
        return None

    def _stat_datetime_value_min(self, state_data: StateData) -> datetime | None:
        if len(state_data.values) > 0:
            return state_data.timestamps[
                state_data.values.index(min(state_data.values))
            ]
        return None

    def _stat_distance_95_percent_of_values(self, state_data: StateData) -> StateType:
        if len(state_data.values) >= 1:
            return 2 * 1.96 * cast(float, self._stat_standard_deviation(state_data))
        return None

    def _stat_distance_99_percent_of_values(self, state_data: StateData) -> StateType:
        if len(state_data.values) >= 1:
            return 2 * 2.58 * cast(float, self._stat_standard_deviation(state_data))
        return None

    def _stat_distance_absolute(self, state_data: StateData) -> StateType:
        if len(state_data.values) > 0:
            return max(state_data.values) - min(state_data.values)
        return None

    def _stat_mean(self, state_data: StateData) -> StateType:
        if len(state_data.values) > 0:
            return statistics.mean(state_data.values)
        return None

    def _stat_mean_circular(self, state_data: StateData) -> StateType:
        if len(state_data.values) > 0:
            sin_sum = sum(math.sin(math.radians(x)) for x in state_data.values)
            cos_sum = sum(math.cos(math.radians(x)) for x in state_data.values)
            return (math.degrees(math.atan2(sin_sum, cos_sum)) + 360) % 360
        return None

    def _stat_median(self, state_data: StateData) -> StateType:
        if len(state_data.values) > 0:
            return statistics.median(state_data.values)
        return None

    def _stat_noisiness(self, state_data: StateData) -> StateType:
        if len(state_data.values) == 1:
            return 0.0
        if len(state_data.values) >= 2:
            return cast(float, self._stat_sum_differences(state_data)) / (
                len(state_data.values) - 1
            )
        return None

    def _stat_percentile(self, state_data: StateData) -> StateType:
        if len(state_data.values) == 1:
            return state_data.values[0]
        if len(state_data.values) >= 2:
            percentiles = statistics.quantiles(
                state_data.values, n=100, method="exclusive"
            )
            return percentiles[self._percentile - 1]
        return None

    def _stat_standard_deviation(self, state_data: StateData) -> StateType:
        if len(state_data.values) == 1:
            return 0.0
        if len(state_data.values) >= 2:
            return statistics.stdev(state_data.values)
        return None

    def _stat_sum(self, state_data: StateData) -> StateType:
        if len(state_data.values) > 0:
            return sum(state_data.values)
        return None

    def _stat_sum_differences(self, state_data: StateData) -> StateType:
        if len(state_data.values) == 1:
            return 0.0
        if len(state_data.values) >= 2:
            return sum(
                abs(j - i)
                for i, j in zip(
                    list(state_data.values), list(state_data.values)[1:], strict=False
                )
            )
        return None

    def _stat_sum_differences_nonnegative(self, state_data: StateData) -> StateType:
        if len(state_data.values) == 1:
            return 0.0
        if len(state_data.values) >= 2:
            return sum(
                (j - i if j >= i else j - 0)
                for i, j in zip(
                    list(state_data.values), list(state_data.values)[1:], strict=False
                )
            )
        return None

    def _stat_total(self, state_data: StateData) -> StateType:
        return self._stat_sum(state_data)

    def _stat_value_max(self, state_data: StateData) -> StateType:
        if len(state_data.values) > 0:
            return max(state_data.values)
        return None

    def _stat_value_min(self, state_data: StateData) -> StateType:
        if len(state_data.values) > 0:
            return min(state_data.values)
        return None

    def _stat_variance(self, state_data: StateData) -> StateType:
        if len(state_data.values) == 1:
            return 0.0
        if len(state_data.values) >= 2:
            return statistics.variance(state_data.values)
        return None

    # Statistics for binary sensor

    def _stat_binary_average_step(self, state_data: StateData) -> StateType:
        return self._stat_time_based_average(STAT_AVERAGE_STEP, state_data, True)

    def _stat_binary_average_timeless(self, state_data: StateData) -> StateType:
        return self._stat_binary_mean(state_data)

    def _stat_binary_count(self, state_data: StateData) -> StateType:
        return len(state_data.values)

    def _stat_binary_count_on(self, state_data: StateData) -> StateType:
        return state_data.values.count(1.0)

    def _stat_binary_count_off(self, state_data: StateData) -> StateType:
        return state_data.values.count(0.0)

    def _stat_binary_datetime_newest(self, state_data: StateData) -> datetime | None:
        return self._stat_datetime_newest(state_data)

    def _stat_binary_datetime_oldest(self, state_data: StateData) -> datetime | None:
        return self._stat_datetime_oldest(state_data)

    def _stat_binary_mean(self, state_data: StateData) -> StateType:
        if len(state_data.values) > 0:
            return 100.0 / len(state_data.values) * state_data.values.count(True)
        return None
