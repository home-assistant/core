"""Numeric integration of data coming from a source sensor over time."""
from __future__ import annotations

from datetime import timedelta

from decimal import Decimal, DecimalException
import logging

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_METHOD,
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TIME_DAYS,
    TIME_HOURS,
    TIME_MINUTES,
    TIME_SECONDS,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

ATTR_SOURCE_ID = "source"

CONF_SOURCE_SENSOR = "source"
CONF_ROUND_DIGITS = "round"
CONF_UNIT_PREFIX = "unit_prefix"
CONF_UNIT_TIME = "unit_time"
CONF_UNIT_OF_MEASUREMENT = "unit"
CONF_MAX_TIMESLICE = "max_timeslice"

TRAPEZOIDAL_METHOD = "trapezoidal"
LEFT_METHOD = "left"
RIGHT_METHOD = "right"
INTEGRATION_METHOD = [TRAPEZOIDAL_METHOD, LEFT_METHOD, RIGHT_METHOD]

# SI Metric prefixes
UNIT_PREFIXES = {None: 1, "k": 10**3, "M": 10**6, "G": 10**9, "T": 10**12}

# SI Time prefixes
UNIT_TIME = {
    TIME_SECONDS: 1,
    TIME_MINUTES: 60,
    TIME_HOURS: 60 * 60,
    TIME_DAYS: 24 * 60 * 60,
}

ICON = "mdi:chart-histogram"

DEFAULT_ROUND = 3

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_UNIT_OF_MEASUREMENT),
    PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_NAME): cv.string,
            vol.Required(CONF_SOURCE_SENSOR): cv.entity_id,
            vol.Optional(CONF_ROUND_DIGITS, default=DEFAULT_ROUND): vol.Coerce(int),
            vol.Optional(CONF_UNIT_PREFIX, default=None): vol.In(UNIT_PREFIXES),
            vol.Optional(CONF_UNIT_TIME, default=TIME_HOURS): vol.In(UNIT_TIME),
            vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
            vol.Optional(CONF_METHOD, default=TRAPEZOIDAL_METHOD): vol.In(
                INTEGRATION_METHOD
            ),
            # No default for the max timeslice, everyone has different sensors
            # with different expected update intervals.
            vol.optional(CONF_MAX_TIMESLICE, default=None): vol.All(
                cv.time_period, cv.positive_timedelta
            ),
        }
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the integration sensor."""
    integral = IntegrationSensor(
        config[CONF_SOURCE_SENSOR],
        config.get(CONF_NAME),
        config[CONF_ROUND_DIGITS],
        config[CONF_UNIT_PREFIX],
        config[CONF_UNIT_TIME],
        config.get(CONF_UNIT_OF_MEASUREMENT),
        config[CONF_METHOD],
        config[CONF_MAX_TIMESLICE],
    )

    async_add_entities([integral])


class IntegrationSensor(RestoreEntity, SensorEntity):
    """Representation of an integration sensor."""

    def __init__(
        self,
        source_entity: str,
        name: str | None,
        round_digits: int,
        unit_prefix: str | None,
        unit_time: str,
        unit_of_measurement: str | None,
        integration_method: str,
        max_timeslice: timedelta | None,
    ) -> None:
        """Initialize the integration sensor."""
        self._sensor_source_id = source_entity
        self._round_digits = round_digits
        self._state = None
        self._method = integration_method
        self._max_timeslice = max_timeslice

        self._name = name if name is not None else f"{source_entity} integral"
        self._unit_template = (
            f"{'' if unit_prefix is None else unit_prefix}{{}}{unit_time}"
        )
        self._unit_of_measurement = unit_of_measurement
        self._unit_prefix = UNIT_PREFIXES[unit_prefix]
        self._unit_time = UNIT_TIME[unit_time]
        self._attr_state_class = SensorStateClass.TOTAL

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if state := await self.async_get_last_state():
            try:
                self._state = Decimal(state.state)
            except (DecimalException, ValueError) as err:
                _LOGGER.warning("Could not restore last state: %s", err)
            else:
                self._attr_device_class = state.attributes.get(ATTR_DEVICE_CLASS)
                if self._unit_of_measurement is None:
                    self._unit_of_measurement = state.attributes.get(
                        ATTR_UNIT_OF_MEASUREMENT
                    )

        @callback
        def calc_integration(event):
            """Handle the sensor state changes."""
            old_state = event.data.get("old_state")
            new_state = event.data.get("new_state")

            # We may want to update our state before an early return,
            # based on the source sensor's unit_of_measurement
            # or device_class.
            update_state = False

            if self._unit_of_measurement is None:
                unit = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
                if unit is not None:
                    self._unit_of_measurement = self._unit_template.format(unit)
                    update_state = True

            if (
                self.device_class is None
                and new_state.attributes.get(ATTR_DEVICE_CLASS)
                == SensorDeviceClass.POWER
            ):
                self._attr_device_class = SensorDeviceClass.ENERGY
                update_state = True

            if update_state:
                self.async_write_ha_state()

            if (
                old_state is None
                or new_state is None
                or old_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            ):
                return

            try:
                # integration as the Riemann integral of previous measures.
                area = 0
                elapsed_time = (
                    new_state.last_updated - old_state.last_updated
                ).total_seconds()

                if self._max_timeslice is not None:
                    # This extra piece of code breaks up the time between the
                    # old and new state into timeslices of a specified
                    # maximum width. This prevents crazy inaccuracies with the
                    # right method of Riemann integration when used with a
                    # dynamic-width timeslice, like when a sensor was at zero
                    # for an extended period of time, and then spiked to a
                    # large value, which would fill that whole time it's been
                    # at zero with the new large value. The default trapezoidal
                    # method is affected by this as well, since it's just the
                    # arithmetic mean of the left and right methods.
                    #
                    # There are two reasons why I didn't just set up a timer to
                    # poll this function at the interval of the max timeslice:
                    # - It's a cycle eater, and I don't like 'em.
                    # - I have no idea how this codebase is organized and it's
                    #   too late in the night for me to go re-learn Python
                    #   again.
                    max_timeslice = self._max_timeslice.total_seconds()
                    
                    # Divide the time that has passed since the last update
                    # into zero or more "max-timeslices" of the specified
                    # width, and the remainder is the last one in the streak of
                    # not having any changes to the value.
                    most_recent_timeslice = elapsed_time % max_timeslice
                    # Find the sum of the lengths of all max-timeslices (which
                    # all have the value of the old state)
                    sum_of_max_timeslices = elapsed_time - most_recent_timeslice

                    # Since all of the max-timeslices by definition have the
                    # same value, all the methods yield the same value.
                    area += Decimal(old_state.state) * Decimal(sum_of_max_timeslices)
                else:
                    # If we're not doing the cool subdivision trick, just glue
                    # the whole time period into one single timeslice and
                    # let the electric kettle wattage spikes destroy our
                    # beautiful trapezoidal integrator.
                    most_recent_timeslice = elapsed_time

                if self._method == TRAPEZOIDAL_METHOD:
                    area += (
                        (Decimal(new_state.state) + Decimal(old_state.state))
                        * Decimal(most_recent_timeslice)
                        / 2
                    )
                elif self._method == LEFT_METHOD:
                    area += Decimal(old_state.state) * Decimal(most_recent_timeslice)
                elif self._method == RIGHT_METHOD:
                    area += Decimal(new_state.state) * Decimal(most_recent_timeslice)

                integral = area / (self._unit_prefix * self._unit_time)
                assert isinstance(integral, Decimal)
            except ValueError as err:
                _LOGGER.warning("While calculating integration: %s", err)
            except DecimalException as err:
                _LOGGER.warning(
                    "Invalid state (%s > %s): %s", old_state.state, new_state.state, err
                )
            except AssertionError as err:
                _LOGGER.error("Could not calculate integral: %s", err)
            else:
                if isinstance(self._state, Decimal):
                    self._state += integral
                else:
                    self._state = integral
                self.async_write_ha_state()

        async_track_state_change_event(
            self.hass, [self._sensor_source_id], calc_integration
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if isinstance(self._state, Decimal):
            return round(self._state, self._round_digits)
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {ATTR_SOURCE_ID: self._sensor_source_id}

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON
