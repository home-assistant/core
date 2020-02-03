"""Numeric derivative of data coming from a source sensor over time."""
from decimal import Decimal, DecimalException
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_SOURCE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.restore_state import RestoreEntity

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

ATTR_SOURCE_ID = "source"

CONF_ROUND_DIGITS = "round"
CONF_UNIT_PREFIX = "unit_prefix"
CONF_UNIT_TIME = "unit_time"
CONF_UNIT = "unit"
CONF_TIME_WINDOW = "time_window"

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
UNIT_TIME = {"s": 1, "min": 60, "h": 60 * 60, "d": 24 * 60 * 60}

ICON = "mdi:chart-line"

DEFAULT_ROUND = 3
DEFAULT_TIME_WINDOW = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_SOURCE): cv.entity_id,
        vol.Optional(CONF_ROUND_DIGITS, default=DEFAULT_ROUND): vol.Coerce(int),
        vol.Optional(CONF_UNIT_PREFIX, default=None): vol.In(UNIT_PREFIXES),
        vol.Optional(CONF_UNIT_TIME, default="h"): vol.In(UNIT_TIME),
        vol.Optional(CONF_UNIT): cv.string,
        vol.Optional(CONF_TIME_WINDOW, default=DEFAULT_TIME_WINDOW): cv.time_period,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the derivative sensor."""
    derivative = DerivativeSensor(
        source_entity=config[CONF_SOURCE],
        name=config.get(CONF_NAME),
        round_digits=config[CONF_ROUND_DIGITS],
        unit_prefix=config[CONF_UNIT_PREFIX],
        unit_time=config[CONF_UNIT_TIME],
        unit_of_measurement=config.get(CONF_UNIT),
        time_window=config[CONF_TIME_WINDOW],
    )

    async_add_entities([derivative])


class DerivativeSensor(RestoreEntity):
    """Representation of an derivative sensor."""

    def __init__(
        self,
        source_entity,
        name,
        round_digits,
        unit_prefix,
        unit_time,
        unit_of_measurement,
        time_window,
    ):
        """Initialize the derivative sensor."""
        self._sensor_source_id = source_entity
        self._round_digits = round_digits
        self._state = 0
        self._state_list = []  # List of tuples with (timestamp, sensor_value)

        self._name = name if name is not None else f"{source_entity} derivative"

        if unit_of_measurement is None:
            final_unit_prefix = "" if unit_prefix is None else unit_prefix
            self._unit_template = f"{final_unit_prefix}{{}}/{unit_time}"
            # we postpone the definition of unit_of_measurement to later
            self._unit_of_measurement = None
        else:
            self._unit_of_measurement = unit_of_measurement

        self._unit_prefix = UNIT_PREFIXES[unit_prefix]
        self._unit_time = UNIT_TIME[unit_time]
        self._time_window = time_window.total_seconds()

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None:
            try:
                self._state = Decimal(state.state)
            except SyntaxError as err:
                _LOGGER.warning("Could not restore last state: %s", err)

        @callback
        def calc_derivative(entity, old_state, new_state):
            """Handle the sensor state changes."""
            if (
                old_state is None
                or old_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
                or new_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
            ):
                return

            now = new_state.last_updated
            # Filter out the tuples that are older than (and outside of the) `time_window`
            self._state_list = [
                (timestamp, state)
                for timestamp, state in self._state_list
                if (now - timestamp).total_seconds() < self._time_window
            ]
            # It can happen that the list is now empty, in that case
            # we use the old_state, because we cannot do anything better.
            if len(self._state_list) == 0:
                self._state_list.append((old_state.last_updated, old_state.state))
            self._state_list.append((new_state.last_updated, new_state.state))

            if self._unit_of_measurement is None:
                unit = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
                self._unit_of_measurement = self._unit_template.format(
                    "" if unit is None else unit
                )

            try:
                # derivative of previous measures.
                last_time, last_value = self._state_list[-1]
                first_time, first_value = self._state_list[0]

                elapsed_time = (last_time - first_time).total_seconds()
                delta_value = Decimal(last_value) - Decimal(first_value)
                derivative = (
                    delta_value
                    / Decimal(elapsed_time)
                    / Decimal(self._unit_prefix)
                    * Decimal(self._unit_time)
                )
                assert isinstance(derivative, Decimal)
            except ValueError as err:
                _LOGGER.warning("While calculating derivative: %s", err)
            except DecimalException as err:
                _LOGGER.warning(
                    "Invalid state (%s > %s): %s", old_state.state, new_state.state, err
                )
            except AssertionError as err:
                _LOGGER.error("Could not calculate derivative: %s", err)
            else:
                self._state = derivative
                self.async_schedule_update_ha_state()

        async_track_state_change(self.hass, self._sensor_source_id, calc_derivative)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(self._state, self._round_digits)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        state_attr = {ATTR_SOURCE_ID: self._sensor_source_id}
        return state_attr

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON
