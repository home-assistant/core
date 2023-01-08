"""Accumulated cost given a utility meter and a price sensor."""
from __future__ import annotations

from decimal import Decimal, DecimalException
import logging

import voluptuous as vol

from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    ATTR_STATE_CLASS,
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.components.sensor.recorder import reset_detected
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import CONF_PRICE_SOURCE_SENSOR, CONF_UTILITY_SOURCE_SENSOR

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

ATTR_LAST_PERIOD = "last_period"

SUPPORTED_STATE_CLASSES = [
    SensorStateClass.MEASUREMENT,
    SensorStateClass.TOTAL,
    SensorStateClass.TOTAL_INCREASING,
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_UTILITY_SOURCE_SENSOR): cv.entity_id,
        vol.Required(CONF_PRICE_SOURCE_SENSOR): cv.entity_id,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Utility Cost config entry."""
    registry = er.async_get(hass)
    # Validate + resolve entity registry id to entity_id
    utility_source_entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_UTILITY_SOURCE_SENSOR]
    )
    price_source_entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_PRICE_SOURCE_SENSOR]
    )

    utility_cost_sensor = UtilityCostSensor(
        name=config_entry.title,
        utility_source_entity=utility_source_entity_id,
        price_source_entity=price_source_entity_id,
        unique_id=config_entry.entry_id,
    )

    async_add_entities([utility_cost_sensor])


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Utility Cost sensor."""
    utility_cost_sensor = UtilityCostSensor(
        name=config.get(CONF_NAME),
        utility_source_entity=config[CONF_UTILITY_SOURCE_SENSOR],
        price_source_entity=config[CONF_PRICE_SOURCE_SENSOR],
        unique_id=config.get(CONF_UNIQUE_ID),
    )

    async_add_entities([utility_cost_sensor])


class UtilityCostSensor(RestoreEntity, SensorEntity):
    """Representation of a Utility Cost sensor."""

    _wrong_state_class_reported = False

    def __init__(
        self,
        *,
        name: str | None,
        utility_source_entity: str,
        price_source_entity: str,
        unique_id: str | None,
    ) -> None:
        """Initialize the Utility Cost sensor."""
        self._attr_unique_id = unique_id
        self._utility_sensor_source_id = utility_source_entity
        self._price_sensor_source_id = price_source_entity
        self._state: Decimal | None = None
        self._unit_of_measurement: str | None = None
        self._last_period = Decimal("0")

        self._attr_name = name
        self._attr_should_poll = False
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL

    def _combine_units(self, utility_unit, price_unit):
        """Combine the price and utility units and return the currency unit.

        Assumes price unit given in <currency>/<utility> and returns <currency>,
        e.g. "EUR/kWh" returns "EUR".
        """
        if not utility_unit:
            _LOGGER.warning("Invalid utility unit (none)")
            return None
        if not price_unit:
            _LOGGER.warning("Invalid price unit (none)")
            return None

        currency, _, per_utility_unit = price_unit.partition("/")
        if not currency:
            _LOGGER.warning("Invalid price unit %s", price_unit)
            return None
        if per_utility_unit == utility_unit:
            return currency

        _LOGGER.warning(
            "Incompatible units, utility %s, price %s, expected price unit %s/%s",
            utility_unit,
            price_unit,
            currency,
            per_utility_unit,
        )
        return None

    def _reset(self) -> None:
        """Reset the cost sensor."""
        _LOGGER.debug("Resetting cost sensor")
        self._last_period = self._state if self._state is not None else Decimal("0")
        self._state = Decimal("0")
        self._attr_last_reset = dt_util.utcnow()

    @callback
    def _update_cost(self, event):
        """Handle the sensor state changes."""
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        _LOGGER.debug(
            "Update cost %s (%s -> %s)",
            self._attr_name,
            old_state.state if old_state is not None else "None",
            new_state.state if new_state is not None else "None",
        )

        invalid_states = [
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ]

        state_class = new_state.attributes.get(ATTR_STATE_CLASS)
        if state_class not in SUPPORTED_STATE_CLASSES:
            if not self._wrong_state_class_reported:
                self._wrong_state_class_reported = True
                _LOGGER.warning(
                    "Found unexpected state_class %s for %s",
                    state_class,
                    new_state.entity_id,
                )
            return

        if new_state is None or new_state.state in invalid_states:
            _LOGGER.debug("Invalid new state")
            return

        price_state = self.hass.states.get(self._price_sensor_source_id)
        if price_state is None or price_state.state in invalid_states:
            _LOGGER.debug("Invalid price state")
            return

        new_unit = self._combine_units(
            new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
            price_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
        )
        if new_unit is None:
            return
        self._unit_of_measurement = new_unit

        if self._state is None:
            # This is the first valid update
            self._reset()

        if old_state is None or old_state.state in invalid_states:
            # Write state in case we reset or updated the unit of measurement
            self.async_write_ha_state()
            return

        if (
            state_class != SensorStateClass.TOTAL_INCREASING
            and new_state.attributes.get(ATTR_LAST_RESET)
            != old_state.attributes.get(ATTR_LAST_RESET)
        ) or (
            state_class == SensorStateClass.TOTAL_INCREASING
            and reset_detected(
                self.hass,
                self._utility_sensor_source_id,
                float(new_state.state),
                float(old_state.state),
                new_state,
            )
        ):
            # Utility meter was reset, reset cost sensor too
            self._reset()
            self.async_write_ha_state()
            return

        try:
            price = Decimal(price_state.state)

            utility_increment = Decimal(new_state.state) - Decimal(old_state.state)
            cost_increment = utility_increment * price

            self._state += cost_increment
            _LOGGER.debug("Cost increment success")

        except DecimalException as err:
            _LOGGER.warning(
                "Invalid cost update (utility %s to %s, price %s): %s",
                old_state.state,
                new_state.state,
                price_state.state,
                err,
            )

        self.async_write_ha_state()

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
                if self._unit_of_measurement is None:
                    self._unit_of_measurement = state.attributes.get(
                        ATTR_UNIT_OF_MEASUREMENT
                    )
                self._last_period = (
                    Decimal(state.attributes[ATTR_LAST_PERIOD])
                    if state.attributes.get(ATTR_LAST_PERIOD)
                    else Decimal("0")
                )

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._utility_sensor_source_id], self._update_cost
            )
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {ATTR_LAST_PERIOD: str(self._last_period)}
