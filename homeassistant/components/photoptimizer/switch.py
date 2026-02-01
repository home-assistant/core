"""Switch platform for Photoptimizer integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PhotoptimizerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Photoptimizer switch entities."""
    coordinator: PhotoptimizerCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([PhotoptimizerSwitch(coordinator, entry)])


class PhotoptimizerSwitch(CoordinatorEntity[PhotoptimizerCoordinator], SwitchEntity):
    """Representation of a Photoptimizer switch."""

    _attr_has_entity_name = True
    _attr_name = "Optimizer enabled"

    def __init__(
        self,
        coordinator: PhotoptimizerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_optimizer_enabled"
        self._attr_is_on = False

    @property
    def icon(self) -> str:
        """Icon of the entity based on state."""
        if self.is_on:
            return "mdi:solar-power"
        return "mdi:solar-power-variant-outline"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._attr_is_on = False
        self.async_write_ha_state()
