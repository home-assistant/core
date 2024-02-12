"""Numeric derivative of data coming from a source sensor over time."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from decimal import Decimal
import logging
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, RestoreSensor, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_SOURCE,
    UnitOfTime,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, State, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, EventType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ROUND_DIGITS,
    CONF_TIME_WINDOW,
    CONF_UNIT,
    CONF_UNIT_PREFIX,
    CONF_UNIT_TIME,
)

_LOGGER = logging.getLogger(__name__)

ATTR_SOURCE_ID = "source"

# SI Metric prefixes
UNIT_PREFIXES: dict[str | None, float] = {
    None: 1,
    "n": 1e-9,
    "µ": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "M": 1e6,
    "G": 1e9,
    "T": 1e12,
}

# SI Time prefixes
UNIT_TIME: dict[UnitOfTime, int] = {
    UnitOfTime.SECONDS: 1,
    UnitOfTime.MINUTES: 60,
    UnitOfTime.HOURS: 60 * 60,
    UnitOfTime.DAYS: 24 * 60 * 60,
}

DEFAULT_ROUND = 3
DEFAULT_TIME_WINDOW = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_SOURCE): cv.entity_id,
        vol.Optional(CONF_ROUND_DIGITS, default=DEFAULT_ROUND): vol.Coerce(int),
        vol.Optional(CONF_UNIT_PREFIX, default=None): vol.In(UNIT_PREFIXES),
        vol.Optional(CONF_UNIT_TIME, default=UnitOfTime.HOURS): vol.In(UNIT_TIME),
        vol.Optional(CONF_UNIT): cv.string,
        vol.Optional(CONF_TIME_WINDOW, default=DEFAULT_TIME_WINDOW): cv.time_period,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Derivative config entry."""
    registry = er.async_get(hass)
    # Validate + resolve entity registry id to entity_id
    source_entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_SOURCE]
    )

    source_entity = registry.async_get(source_entity_id)
    dev_reg = dr.async_get(hass)
    # Resolve source entity device
    if (
        (source_entity is not None)
        and (source_entity.device_id is not None)
        and (
            (
                device := dev_reg.async_get(
                    device_id=source_entity.device_id,
                )
            )
            is not None
        )
    ):
        device_info = DeviceInfo(
            identifiers=device.identifiers,
            connections=device.connections,
        )
    else:
        device_info = None

    if (unit_prefix := config_entry.options.get(CONF_UNIT_PREFIX)) == "none":
        # Before we had support for optional selectors, "none" was used for selecting nothing
        unit_prefix = None

    derivative_sensor = DerivativeSensor(
        name=config_entry.title,
        round_digits=int(config_entry.options[CONF_ROUND_DIGITS]),
        source_entity=source_entity_id,
        time_window=cv.time_period_dict(config_entry.options[CONF_TIME_WINDOW]),
        unique_id=config_entry.entry_id,
        unit_of_measurement=None,
        unit_prefix=unit_prefix,
        unit_time=config_entry.options[CONF_UNIT_TIME],
        device_info=device_info,
    )

    async_add_entities([derivative_sensor])


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the derivative sensor."""
    derivative = DerivativeSensor(
        name=config.get(CONF_NAME),
        round_digits=config[CONF_ROUND_DIGITS],
        source_entity=config[CONF_SOURCE],
        time_window=config[CONF_TIME_WINDOW],
        unit_of_measurement=config.get(CONF_UNIT),
        unit_prefix=config[CONF_UNIT_PREFIX],
        unit_time=config[CONF_UNIT_TIME],
        unique_id=None,
    )

    async_add_entities([derivative])


class DerivativeSensor(RestoreSensor, SensorEntity):
    """Representation of a derivative sensor.

    Design of the class:
    - If time_window is given, the derivative is at all times equal to the difference between the values at the "ends" of the
      time_window divided by the number of seconds in time_window, and then scaled by unit_time and unit_prefix. This value changes
      when the state at either of those ends change:
      - When a new state change happens, the value of the new state is the value at the "young" end of the time_window, and thus the derivative value changes.
      - When a state becomes older than time_window, the the value of this state is now the value at the "old" end of the time_window, and thus the derivative value changes.
      Thus, the derivative changes twice per state change of the source sensor; once when the new state enter time_window, and once
      when it leaves it. To accommodate triggering on the "leave" event, a queue of states is kept. This queue contains all states
      with a last_changed datetime which are inside time_window from now, and 1 older state, which represents the value at the "old"
      end of time_window. Therefore, after at least one state change occurred, the queue will always contain at least 1 state.
    - How the queue is filled, popped and how the relevant callbacks are created is taken directly from the Statistics integration.
    - If time_window is not given (or is 0 seconds), then this sensor post-calculates the derivative, meaning a state change from
      (old_datetime, old_value) to (new_datetime, new_value) will set the state
        (new_datetime, (new_value - old_value)/(new_datetime - old_datetime))
      This means that the average derivative value in the interval [old_datetime, new_datetime] is calculated and put as sensor
      state on timestamp new_datetime. This does not coincide with graph plotting of HA, which may be counterintuitive.
      - This is facilitated by bounding the length of the queue to 2.
    """

    _attr_translation_key = "derivative"
    _attr_should_poll = False

    def __init__(
        self,
        *,
        name: str | None,
        round_digits: int,
        source_entity: str,
        time_window: timedelta,
        unit_of_measurement: str | None,
        unit_prefix: str | None,
        unit_time: UnitOfTime,
        unique_id: str | None,
        device_info: DeviceInfo | None = None,
    ) -> None:
        """Initialize the derivative sensor."""
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._sensor_source_id = source_entity
        self._round_digits = round_digits
        self._state: float | int | Decimal = 0

        self._attr_name = name if name is not None else f"{source_entity} derivative"
        self._attr_extra_state_attributes = {ATTR_SOURCE_ID: source_entity}

        if unit_of_measurement is None:
            final_unit_prefix = "" if unit_prefix is None else unit_prefix
            self._unit_template = f"{final_unit_prefix}{{}}/{unit_time}"
            # we postpone the definition of unit_of_measurement to later
            self._attr_native_unit_of_measurement = None
        else:
            self._attr_native_unit_of_measurement = unit_of_measurement

        self._unit_prefix = UNIT_PREFIXES[unit_prefix]
        self._unit_time = UNIT_TIME[unit_time]

        self._time_window = time_window

        max_queue_len = None if time_window else 2
        self._states: deque[tuple[float, datetime]] = deque(maxlen=max_queue_len)

        self._update_listener: CALLBACK_TYPE | None = None

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        restored_data = await self.async_get_last_sensor_data()
        if restored_data:
            self._attr_native_unit_of_measurement = (
                restored_data.native_unit_of_measurement
            )
            try:
                self._state = Decimal(restored_data.native_value)  # type: ignore[arg-type]
            except SyntaxError as err:
                _LOGGER.warning("Could not restore last state: %s", err)

        @callback
        def async_sensor_state_listener(
            event: EventType[EventStateChangedData],
        ) -> None:
            """Handle the sensor state changes."""
            new_state = event.data["new_state"]
            if new_state is None:
                return

            if self.native_unit_of_measurement is None:
                unit = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
                self._attr_native_unit_of_measurement = self._unit_template.format(
                    "" if unit is None else unit
                )

            self._add_state_to_queue(new_state)
            self.async_schedule_update_ha_state(True)

        async def async_sensor_startup(_: HomeAssistant) -> None:
            """Add listener."""
            _LOGGER.debug(
                "Startup for %s with source %s", self.entity_id, self._sensor_source_id
            )

            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    [self._sensor_source_id],
                    async_sensor_state_listener,
                )
            )

        self.async_on_remove(async_at_start(self.hass, async_sensor_startup))

    def _add_state_to_queue(self, new_state: State) -> None:
        """Add the state to the queue."""

        try:
            self._states.append((float(new_state.state), new_state.last_updated))
        except ValueError:
            _LOGGER.error(
                "%s: parsing error. Expected number, but received '%s'",
                self.entity_id,
                new_state.state,
            )

    def _purge_old_states(self) -> None:
        """Remove all states except 1 which are older than the time window."""
        now = dt_util.utcnow()

        _LOGGER.debug(
            "%s: purging records older than %s(%s)",
            self.entity_id,
            dt_util.as_local(now - self._time_window),
            self._time_window,
        )

        while len(self._states) > 1 and (now - self._states[1][1]) > self._time_window:
            _LOGGER.debug(
                "%s: purging record with datetime %s(age: %s, UTC: %s) and value %s",
                self.entity_id,
                dt_util.as_local(self._states[0][1]),
                (now - self._states[0][1]),
                dt_util.as_utc(self._states[0][1]),
                self._states[0][0],
            )
            self._states.popleft()

    def _next_to_purge_timestamp(self) -> datetime | None:
        """Find the timestamp when the next purge would occur."""
        if len(self._states) > 1 and self._time_window:
            # Take the oldest entry from the states list that is within the time_window
            # and add the configured time_window length.
            # If executed after purging old states, the result is the next timestamp
            # in the future when the oldest state will expire.
            return self._states[1][1] + self._time_window
        return None

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("%s: updating derivative", self.entity_id)
        if self._time_window:
            self._purge_old_states()

        self._update_value()

        # If time_window is set, ensure to update again after the defined interval.
        if timestamp := self._next_to_purge_timestamp():
            _LOGGER.debug("%s: scheduling update at %s", self.entity_id, timestamp)
            if self._update_listener:
                self._update_listener()
                self._update_listener = None

            @callback
            def _scheduled_update(now: datetime) -> None:
                """Timer callback for sensor update."""
                _LOGGER.debug(
                    "%s: executing scheduled update at time %s", self.entity_id, now
                )
                self.async_schedule_update_ha_state(True)
                self._update_listener = None

            self._update_listener = async_track_point_in_utc_time(
                self.hass, _scheduled_update, timestamp
            )

    def _update_value(self) -> None:
        """Front to calculate the derivative value."""

        if len(self._states) == 0:
            self._state = 0

        # If there is only 1 value, the states are equal
        old_state: tuple[float, datetime] = self._states[0]
        new_state: tuple[float, datetime] = self._states[-1]
        value_difference: float = new_state[0] - old_state[0]

        time_difference: float = 1.0
        if self._time_window:
            time_difference = self._time_window.total_seconds()
        elif len(self._states) == 1:
            # It doesn't matter what time_difference is as in this case value_difference == 0.0, as long as it is not 0.0 because that results in ZeroDivisionError instead of the desired 0.0
            time_difference = 1.0
        else:
            time_difference = (new_state[1] - old_state[1]).total_seconds()

        self._state = (
            value_difference / time_difference / self._unit_prefix * self._unit_time
        )

        _LOGGER.debug(
            "%s: Calculate derivative: %s -> %s: %.12f / %.12f / %.12f * %.12f = %.12f",
            self.entity_id,
            old_state,
            new_state,
            value_difference,
            time_difference,
            self._unit_prefix,
            self._unit_time,
            self._state,
        )

    @property
    def native_value(self) -> float | int | Decimal:
        """Return the state of the sensor."""
        value = round(self._state, self._round_digits)
        if TYPE_CHECKING:
            assert isinstance(value, (float, int, Decimal))
        return value
