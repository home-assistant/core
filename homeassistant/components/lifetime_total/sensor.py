"""Sensor platform for Lifetime Total integration."""
from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, DecimalException
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Lifetime Total config entry."""
    registry = er.async_get(hass)
    entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_ID]
    )
    name = config_entry.title
    unique_id = config_entry.entry_id

    async_add_entities([LifetimeTotalSensorEntity(unique_id, name, entity_id)])


class LifetimeTotalSensorEntity(RestoreEntity, SensorEntity):
    """Lifetime Total Sensor."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_should_poll = False

    def __init__(self, unique_id: str, name: str, wrapped_entity_id: str) -> None:
        """Initialize Lifetime Total Sensor."""
        super().__init__()
        self._wrapped_entity_id = wrapped_entity_id
        self._attr_name = name
        self._attr_unique_id = unique_id

        self._value: Decimal = Decimal(0)
        self._prev_value: Decimal = Decimal(0)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if state := await self.async_get_last_state():
            try:
                self._value = Decimal(state.state)
            except (DecimalException, ValueError) as err:
                _LOGGER.warning(
                    "%s could not restore last state %s: %s",
                    self.entity_id,
                    state.state,
                    err,
                )
            try:
                last_reading = state.attributes.get("last_reading")
                self._prev_value = Decimal(last_reading or 0)
            except (DecimalException, ValueError) as err:
                _LOGGER.warning(
                    "%s could not restore previous reading %s: %s",
                    self.entity_id,
                    last_reading,
                    err,
                )
            else:
                self._attr_device_class = state.attributes.get(ATTR_DEVICE_CLASS)
                self._attr_unit_of_measurement = state.attributes.get(
                    ATTR_UNIT_OF_MEASUREMENT
                )
        else:
            self._value = Decimal(0)
            self._prev_value = Decimal(0)

        @callback
        def calc_total(event: Event) -> None:
            """Handle the sensor state changes."""
            new_state: State | None = event.data.get("new_state")

            if new_state is None or new_state.state in (
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ):
                return

            try:
                new_value = Decimal(new_state.state)
                if new_value < self._prev_value:
                    delta = new_value
                else:
                    delta = new_value - self._prev_value
            except ValueError as err:
                _LOGGER.warning("While calculating total: %s", err)
            except DecimalException as err:
                _LOGGER.warning("Invalid state (%s): %s", new_state.state, err)
            else:
                self._value += delta
                self._prev_value = new_value

                if unit := new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT):
                    self._attr_native_unit_of_measurement = unit

                if device_class := new_state.attributes.get(ATTR_DEVICE_CLASS):
                    self._attr_device_class = device_class

                self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._wrapped_entity_id], calc_total
            )
        )
        state = self.hass.states.get(self._wrapped_entity_id)
        state_event = Event(
            "", {"entity_id": self._wrapped_entity_id, "new_state": state}
        )
        calc_total(state_event)

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return float(self._value)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return entity specific state attributes."""
        return {
            "last_reading": float(self._prev_value),
        }
