"""The number platform for rainbird."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RainbirdUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry for a Rain Bird number platform."""
    async_add_entities(
        [
            RainDelayNumber(
                hass.data[DOMAIN][config_entry.entry_id],
            )
        ]
    )


class RainDelayNumber(CoordinatorEntity[RainbirdUpdateCoordinator], NumberEntity):
    """A number implemnetaiton for the rain delay."""

    _attr_native_min_value = 0
    _attr_native_max_value = 14
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_icon = "mdi:water-off"
    _attr_name = "Rain delay"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RainbirdUpdateCoordinator,
    ) -> None:
        """Initialize the Rain Bird sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}-rain-delay"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the sensor."""
        return self.coordinator.data.rain_delay

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.coordinator.controller.set_rain_delay(value)
