"""Numeric integration of data coming from a source sensor over time."""
from __future__ import annotations

from decimal import Decimal, DecimalException
import logging

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_METHOD,
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TIME_HOURS,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_ROUND_DIGITS,
    CONF_SOURCE_SENSOR,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_UNIT_PREFIX,
    CONF_UNIT_TIME,
    DEFAULT_ROUND,
    INTEGRATION_METHOD,
    LEFT_METHOD,
    PLATFORM_UNIT_PREFIXES,
    RIGHT_METHOD,
    TRAPEZOIDAL_METHOD,
    UNIT_TIME,
)

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

ATTR_SOURCE_ID = "source"

ICON = "mdi:chart-histogram"

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_UNIT_OF_MEASUREMENT),
    PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_NAME): cv.string,
            vol.Required(CONF_SOURCE_SENSOR): cv.entity_id,
            vol.Optional(CONF_ROUND_DIGITS, default=DEFAULT_ROUND): vol.Coerce(int),
            vol.Optional(CONF_UNIT_PREFIX, default=None): vol.In(
                PLATFORM_UNIT_PREFIXES
            ),
            vol.Optional(CONF_UNIT_TIME, default=TIME_HOURS): vol.In(UNIT_TIME),
            vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
            vol.Optional(CONF_METHOD, default=TRAPEZOIDAL_METHOD): vol.In(
                INTEGRATION_METHOD
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
    )

    async_add_entities([integral])


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the integration sensor platform."""
    integral = IntegrationSensor(
        entry.data[CONF_SOURCE_SENSOR],
        entry.title,
        entry.data[CONF_ROUND_DIGITS],
        entry.data.get(CONF_UNIT_PREFIX),
        entry.data[CONF_UNIT_TIME],
        None,
        entry.data[CONF_METHOD],
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
    ) -> None:
        """Initialize the integration sensor."""
        self._sensor_source_id = source_entity
        self._round_digits = round_digits
        self._state = None
        self._method = integration_method

        self._name = name if name is not None else f"{source_entity} integral"
        self._unit_template = (
            f"{'' if unit_prefix is None else unit_prefix}{{}}{unit_time}"
        )
        self._unit_of_measurement = unit_of_measurement
        self._unit_prefix = PLATFORM_UNIT_PREFIXES[unit_prefix]
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

                if self._method == TRAPEZOIDAL_METHOD:
                    area = (
                        (Decimal(new_state.state) + Decimal(old_state.state))
                        * Decimal(elapsed_time)
                        / 2
                    )
                elif self._method == LEFT_METHOD:
                    area = Decimal(old_state.state) * Decimal(elapsed_time)
                elif self._method == RIGHT_METHOD:
                    area = Decimal(new_state.state) * Decimal(elapsed_time)

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
