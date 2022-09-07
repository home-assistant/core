"""Numeric derivative of data coming from a source sensor over time."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, DecimalException
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_SOURCE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TIME_DAYS,
    TIME_HOURS,
    TIME_MINUTES,
    TIME_SECONDS,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_ROUND_DIGITS,
    CONF_TIME_WINDOW,
    CONF_UNIT,
    CONF_UNIT_PREFIX,
    CONF_UNIT_TIME,
)

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

ATTR_SOURCE_ID = "source"

# SI Metric prefixes
UNIT_PREFIXES = {
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
UNIT_TIME = {
    TIME_SECONDS: 1,
    TIME_MINUTES: 60,
    TIME_HOURS: 60 * 60,
    TIME_DAYS: 24 * 60 * 60,
}

ICON = "mdi:chart-line"

DEFAULT_ROUND = 3
DEFAULT_TIME_WINDOW = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_SOURCE): cv.entity_id,
        vol.Optional(CONF_ROUND_DIGITS, default=DEFAULT_ROUND): vol.Coerce(int),
        vol.Optional(CONF_UNIT_PREFIX, default=None): vol.In(UNIT_PREFIXES),
        vol.Optional(CONF_UNIT_TIME, default=TIME_HOURS): vol.In(UNIT_TIME),
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

    unit_prefix = config_entry.options[CONF_UNIT_PREFIX]
    if unit_prefix == "none":
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


class DerivativeSensor(RestoreEntity, SensorEntity):
    """Representation of an derivative sensor."""

    _attr_icon = ICON
    _attr_should_poll = False

    def __init__(
        self,
        *,
        name,
        round_digits,
        source_entity,
        time_window,
        unit_of_measurement,
        unit_prefix,
        unit_time,
        unique_id,
    ):
        """Initialize the derivative sensor."""
        self._attr_unique_id = unique_id
        self._sensor_source_id = source_entity
        self._round_digits = round_digits
        self._state = 0
        # List of tuples with (timestamp_start, timestamp_end, derivative)
        self._state_list: list[tuple[datetime, datetime, Decimal]] = []

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
        self._time_window = time_window.total_seconds()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is not None:
            try:
                self._state = Decimal(state.state)
            except SyntaxError as err:
                _LOGGER.warning("Could not restore last state: %s", err)

        @callback
        def calc_derivative(event: Event) -> None:
            """Handle the sensor state changes."""
            old_state: State | None
            new_state: State | None
            if (
                (old_state := event.data.get("old_state")) is None
                or old_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                or (new_state := event.data.get("new_state")) is None
                or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            ):
                return

            if self.native_unit_of_measurement is None:
                unit = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
                self._attr_native_unit_of_measurement = self._unit_template.format(
                    "" if unit is None else unit
                )

            # filter out all derivatives older than `time_window` from our window list
            self._state_list = [
                (time_start, time_end, state)
                for time_start, time_end, state in self._state_list
                if (new_state.last_updated - time_end).total_seconds()
                < self._time_window
            ]

            try:
                elapsed_time = (
                    new_state.last_updated - old_state.last_updated
                ).total_seconds()
                delta_value = Decimal(new_state.state) - Decimal(old_state.state)
                new_derivative = (
                    delta_value
                    / Decimal(elapsed_time)
                    / Decimal(self._unit_prefix)
                    * Decimal(self._unit_time)
                )

            except ValueError as err:
                _LOGGER.warning("While calculating derivative: %s", err)
            except DecimalException as err:
                _LOGGER.warning(
                    "Invalid state (%s > %s): %s", old_state.state, new_state.state, err
                )
            except AssertionError as err:
                _LOGGER.error("Could not calculate derivative: %s", err)

            # add latest derivative to the window list
            self._state_list.append(
                (old_state.last_updated, new_state.last_updated, new_derivative)
            )

            def calculate_weight(start, end, now):
                window_start = now - timedelta(seconds=self._time_window)
                if start < window_start:
                    weight = (end - window_start).total_seconds() / self._time_window
                else:
                    weight = (end - start).total_seconds() / self._time_window
                return weight

            # If outside of time window just report derivative (is the same as modeling it in the window),
            # otherwise take the weighted average with the previous derivatives
            if elapsed_time > self._time_window:
                derivative = new_derivative
            else:
                derivative = Decimal(0)
                for (start, end, value) in self._state_list:
                    weight = calculate_weight(start, end, new_state.last_updated)
                    derivative = derivative + (value * Decimal(weight))

            self._state = derivative
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._sensor_source_id, calc_derivative
            )
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return round(self._state, self._round_digits)
