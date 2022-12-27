"""Numeric integration of data coming from a source sensor over time."""
from __future__ import annotations

from decimal import Decimal, DecimalException
import logging
from typing import Final

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
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTime,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
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
    INTEGRATION_METHODS,
    METHOD_LEFT,
    METHOD_RIGHT,
    METHOD_TRAPEZOIDAL,
)

_LOGGER = logging.getLogger(__name__)

ATTR_SOURCE_ID: Final = "source"

# SI Metric prefixes
UNIT_PREFIXES = {None: 1, "k": 10**3, "M": 10**6, "G": 10**9, "T": 10**12}

# SI Time prefixes
UNIT_TIME = {
    UnitOfTime.SECONDS: 1,
    UnitOfTime.MINUTES: 60,
    UnitOfTime.HOURS: 60 * 60,
    UnitOfTime.DAYS: 24 * 60 * 60,
}

DEFAULT_ROUND = 3

PLATFORM_SCHEMA = vol.All(
    cv.removed(CONF_UNIT_OF_MEASUREMENT),
    PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Required(CONF_SOURCE_SENSOR): cv.entity_id,
            vol.Optional(CONF_ROUND_DIGITS, default=DEFAULT_ROUND): vol.Coerce(int),
            vol.Optional(CONF_UNIT_PREFIX, default=None): vol.In(UNIT_PREFIXES),
            vol.Optional(CONF_UNIT_TIME, default=UnitOfTime.HOURS): vol.In(UNIT_TIME),
            vol.Remove(CONF_UNIT_OF_MEASUREMENT): cv.string,
            vol.Optional(CONF_METHOD, default=METHOD_TRAPEZOIDAL): vol.In(
                INTEGRATION_METHODS
            ),
        }
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Integration - Riemann sum integral config entry."""
    registry = er.async_get(hass)
    # Validate + resolve entity registry id to entity_id
    source_entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_SOURCE_SENSOR]
    )

    unit_prefix = config_entry.options[CONF_UNIT_PREFIX]
    if unit_prefix == "none":
        unit_prefix = None

    integral = IntegrationSensor(
        integration_method=config_entry.options[CONF_METHOD],
        name=config_entry.title,
        round_digits=int(config_entry.options[CONF_ROUND_DIGITS]),
        source_entity=source_entity_id,
        unique_id=config_entry.entry_id,
        unit_prefix=unit_prefix,
        unit_time=config_entry.options[CONF_UNIT_TIME],
    )

    async_add_entities([integral])


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the integration sensor."""
    integral = IntegrationSensor(
        integration_method=config[CONF_METHOD],
        name=config.get(CONF_NAME),
        round_digits=config[CONF_ROUND_DIGITS],
        source_entity=config[CONF_SOURCE_SENSOR],
        unique_id=config.get(CONF_UNIQUE_ID),
        unit_prefix=config[CONF_UNIT_PREFIX],
        unit_time=config[CONF_UNIT_TIME],
    )

    async_add_entities([integral])


class IntegrationSensor(RestoreEntity, SensorEntity):
    """Representation of an integration sensor."""

    _attr_state_class = SensorStateClass.TOTAL
    _attr_should_poll = False

    def __init__(
        self,
        *,
        integration_method: str,
        name: str | None,
        round_digits: int,
        source_entity: str,
        unique_id: str | None,
        unit_prefix: str | None,
        unit_time: UnitOfTime,
    ) -> None:
        """Initialize the integration sensor."""
        self._attr_unique_id = unique_id
        self._sensor_source_id = source_entity
        self._round_digits = round_digits
        self._state: Decimal | None = None
        self._method = integration_method

        self._attr_name = name if name is not None else f"{source_entity} integral"
        self._unit_template = f"{'' if unit_prefix is None else unit_prefix}{{}}"
        self._unit_of_measurement: str | None = None
        self._unit_prefix = UNIT_PREFIXES[unit_prefix]
        self._unit_time = UNIT_TIME[unit_time]
        self._unit_time_str = unit_time
        self._attr_icon = "mdi:chart-histogram"
        self._attr_extra_state_attributes = {ATTR_SOURCE_ID: source_entity}

    def _unit(self, source_unit: str) -> str:
        """Derive unit from the source sensor, SI prefix and time unit."""
        unit_time = self._unit_time_str
        if source_unit.endswith(f"/{unit_time}"):
            integral_unit = source_unit[0 : (-(1 + len(unit_time)))]
        else:
            integral_unit = f"{source_unit}{unit_time}"

        return self._unit_template.format(integral_unit)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if state := await self.async_get_last_state():
            try:
                self._state = Decimal(state.state)
            except (DecimalException, ValueError) as err:
                _LOGGER.warning(
                    "%s could not restore last state %s: %s",
                    self.entity_id,
                    state.state,
                    err,
                )
            else:
                self._attr_device_class = state.attributes.get(ATTR_DEVICE_CLASS)
                if self._unit_of_measurement is None:
                    self._unit_of_measurement = state.attributes.get(
                        ATTR_UNIT_OF_MEASUREMENT
                    )

        @callback
        def calc_integration(event: Event) -> None:
            """Handle the sensor state changes."""
            old_state: State | None = event.data.get("old_state")
            new_state: State | None = event.data.get("new_state")

            if new_state is None or new_state.state in (
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ):
                return

            # We may want to update our state before an early return,
            # based on the source sensor's unit_of_measurement
            # or device_class.
            update_state = False
            unit = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            if unit is not None:
                new_unit_of_measurement = self._unit(unit)
                if self._unit_of_measurement != new_unit_of_measurement:
                    self._unit_of_measurement = new_unit_of_measurement
                    update_state = True

            if (
                self.device_class is None
                and new_state.attributes.get(ATTR_DEVICE_CLASS)
                == SensorDeviceClass.POWER
            ):
                self._attr_device_class = SensorDeviceClass.ENERGY
                self._attr_icon = None
                update_state = True

            if update_state:
                self.async_write_ha_state()

            if old_state is None or old_state.state in (
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ):
                return

            try:
                # integration as the Riemann integral of previous measures.
                area = Decimal(0)
                elapsed_time = (
                    new_state.last_updated - old_state.last_updated
                ).total_seconds()

                if self._method == METHOD_TRAPEZOIDAL:
                    area = (
                        (Decimal(new_state.state) + Decimal(old_state.state))
                        * Decimal(elapsed_time)
                        / 2
                    )
                elif self._method == METHOD_LEFT:
                    area = Decimal(old_state.state) * Decimal(elapsed_time)
                elif self._method == METHOD_RIGHT:
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

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._sensor_source_id], calc_integration
            )
        )

    @property
    def native_value(self) -> Decimal | None:
        """Return the state of the sensor."""
        if isinstance(self._state, Decimal):
            return round(self._state, self._round_digits)
        return self._state

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement
