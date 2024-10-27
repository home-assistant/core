"""The number platform for rainbird."""

from __future__ import annotations

import logging

from pyrainbird.exceptions import RainbirdApiException, RainbirdDeviceBusyException

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
                hass.data[DOMAIN][config_entry.entry_id].coordinator,
            )
        ]
    )


class RainDelayNumber(CoordinatorEntity[RainbirdUpdateCoordinator], NumberEntity):
    """A number implementation for the rain delay."""

    _attr_native_min_value = 0
    _attr_native_max_value = 14
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_translation_key = "rain_delay"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RainbirdUpdateCoordinator,
    ) -> None:
        """Initialize the Rain Bird sensor."""
        super().__init__(coordinator)
        if coordinator.unique_id is not None:
            self._attr_unique_id = f"{coordinator.unique_id}-rain-delay"
            self._attr_device_info = coordinator.device_info
        else:
            self._attr_name = f"{coordinator.device_name} Rain delay"

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the sensor."""
        return self.coordinator.data.rain_delay

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        try:
            await self.coordinator.controller.set_rain_delay(value)
        except RainbirdDeviceBusyException as err:
            raise HomeAssistantError(
                "Rain Bird device is busy; Wait and try again"
            ) from err
        except RainbirdApiException as err:
            raise HomeAssistantError("Rain Bird device failure") from err
