"""Casper Glow integration binary sensor platform."""

from __future__ import annotations

from pycasperglow import GlowState

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CasperGlowConfigEntry, CasperGlowCoordinator
from .entity import CasperGlowEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CasperGlowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform for Casper Glow."""
    async_add_entities([CasperGlowPausedBinarySensor(entry.runtime_data)])


class CasperGlowPausedBinarySensor(CasperGlowEntity, BinarySensorEntity):
    """Binary sensor indicating whether the Casper Glow dimming is paused."""

    _attr_translation_key = "paused"

    def __init__(self, coordinator: CasperGlowCoordinator) -> None:
        """Initialize the paused binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{format_mac(coordinator.device.address)}_paused"
        if coordinator.device.state.is_paused is not None:
            self._attr_is_on = coordinator.device.state.is_paused

    async def async_added_to_hass(self) -> None:
        """Register state update callback when entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._device.register_callback(self._async_handle_state_update)
        )

    @callback
    def _async_handle_state_update(self, state: GlowState) -> None:
        """Handle a state update from the device."""
        if state.is_paused is not None:
            self._attr_is_on = state.is_paused
        self.async_write_ha_state()
