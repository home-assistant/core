"""Switch platform for Indevolt integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IndevoltConfigEntry
from .coordinator import IndevoltCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndevoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch entities from a config entry."""
    coordinator = entry.runtime_data

    # Add generation 1 entities
    entities: list[IndevoltSwitchEntity] = []

    # Add generation 2 entities (if applicable)
    if entry.data.get("generation", 1) != 1:
        entities.extend(
            [
                GridChargingSwitch(coordinator, entry),
            ]
        )

    async_add_entities(entities)


class IndevoltSwitchEntity(CoordinatorEntity[IndevoltCoordinator], SwitchEntity):
    """Base class for Indevolt switch entities."""

    _attr_has_entity_name = True
    coordinator: IndevoltCoordinator

    def __init__(
        self, coordinator: IndevoltCoordinator, config_entry: IndevoltConfigEntry
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator

        name_suffix = (self._attr_translation_key or "").replace(" ", "_").lower()
        self._attr_unique_id = f"{config_entry.entry_id}_{name_suffix}"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        if self.coordinator.data:
            value = self._get_switch_state()
            return bool(value) if value is not None else None
        return None

    def _get_write_key(self) -> str:
        """Get the data point (key) for writing to this entity."""
        raise NotImplementedError

    def _get_switch_state(self) -> bool:
        """Get the current switch state for this entity."""
        raise NotImplementedError

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.coordinator.async_push_data(self._get_write_key(), 1)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on %s: %s", self.name, err)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.coordinator.async_push_data(self._get_write_key(), 0)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off %s: %s", self.name, err)
            raise


class GridChargingSwitch(IndevoltSwitchEntity):
    """Switch for Grid Charging."""

    _attr_translation_key = "grid_charging"

    def _get_write_key(self) -> str:
        """Get the data point (key) for writing Grid Charging state."""
        return "1143"

    def _get_switch_state(self) -> bool:
        """Get the current switch state for this entity."""
        val = self.coordinator.data.get("2618")
        return val != 1000
