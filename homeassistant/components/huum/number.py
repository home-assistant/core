"""Control for steamer."""

from __future__ import annotations

import logging

from huum.const import SaunaStatus

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONFIG_STEAMER, CONFIG_STEAMER_AND_LIGHT
from .coordinator import HuumConfigEntry, HuumDataUpdateCoordinator
from .entity import HuumBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HuumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up steamer if applicable."""
    coordinator = config_entry.runtime_data

    # Light is configured for this sauna.
    if coordinator.data.config in [CONFIG_STEAMER, CONFIG_STEAMER_AND_LIGHT]:
        async_add_entities([HuumSteamer(coordinator)])


class HuumSteamer(HuumBaseEntity, NumberEntity):
    """Representation of a steamer."""

    _attr_translation_key = "humidity"
    _attr_native_max_value = 10
    _attr_native_min_value = 0
    _attr_native_step = 1

    def __init__(self, coordinator: HuumDataUpdateCoordinator) -> None:
        """Initialize the steamer."""
        super().__init__(coordinator)

        self._attr_unique_id = coordinator.config_entry.entry_id

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self.coordinator.data.humidity

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        target_temperature = self.coordinator.data.target_temperature
        if (
            not target_temperature
            or self.coordinator.data.status != SaunaStatus.ONLINE_HEATING
        ):
            return

        await self.coordinator.huum.turn_on(
            temperature=target_temperature, humidity=int(value)
        )
        await self.coordinator.async_refresh()
