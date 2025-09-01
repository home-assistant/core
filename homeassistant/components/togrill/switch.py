"""Support for switch entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ToGrillConfigEntry
from .coordinator import ToGrillCoordinator
from .entity import ToGrillEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ToGrillConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch based on a config entry."""

    coordinator = entry.runtime_data

    async_add_entities([ToGrillSwitch(coordinator)])


class ToGrillSwitch(ToGrillEntity, SwitchEntity):
    """Representation of a switch."""

    def __init__(
        self,
        coordinator: ToGrillCoordinator,
    ) -> None:
        """Initialize."""

        super().__init__(coordinator, None)
        self._attr_unique_id = f"{coordinator.address}_active"
        self._attr_translation_key = "active"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.active is not None

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.coordinator.active is True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.coordinator.async_activate()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.async_deactivate()
