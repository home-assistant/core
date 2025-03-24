"""Support for Modern Forms switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import modernforms_exception_handler
from .const import DOMAIN
from .coordinator import ModernFormsDataUpdateCoordinator
from .entity import ModernFormsDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Modern Forms switch based on a config entry."""
    coordinator: ModernFormsDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    switches = [
        ModernFormsAwaySwitch(entry.entry_id, coordinator),
        ModernFormsAdaptiveLearningSwitch(entry.entry_id, coordinator),
    ]
    async_add_entities(switches)


class ModernFormsSwitch(ModernFormsDeviceEntity, SwitchEntity):
    """Defines a Modern Forms switch."""

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: ModernFormsDataUpdateCoordinator,
        key: str,
    ) -> None:
        """Initialize Modern Forms switch."""
        self._key = key
        super().__init__(entry_id=entry_id, coordinator=coordinator)
        self._attr_unique_id = f"{self.coordinator.data.info.mac_address}_{self._key}"


class ModernFormsAwaySwitch(ModernFormsSwitch):
    """Defines a Modern Forms Away mode switch."""

    _attr_translation_key = "away_mode"

    def __init__(
        self, entry_id: str, coordinator: ModernFormsDataUpdateCoordinator
    ) -> None:
        """Initialize Modern Forms Away mode switch."""
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            key="away_mode",
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return bool(self.coordinator.data.state.away_mode_enabled)

    @modernforms_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the Modern Forms Away mode switch."""
        await self.coordinator.modern_forms.away(away=False)

    @modernforms_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the Modern Forms Away mode switch."""
        await self.coordinator.modern_forms.away(away=True)


class ModernFormsAdaptiveLearningSwitch(ModernFormsSwitch):
    """Defines a Modern Forms Adaptive Learning switch."""

    _attr_translation_key = "adaptive_learning"

    def __init__(
        self, entry_id: str, coordinator: ModernFormsDataUpdateCoordinator
    ) -> None:
        """Initialize Modern Forms Adaptive Learning switch."""
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            key="adaptive_learning",
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return bool(self.coordinator.data.state.adaptive_learning_enabled)

    @modernforms_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the Modern Forms Adaptive Learning switch."""
        await self.coordinator.modern_forms.adaptive_learning(adaptive_learning=False)

    @modernforms_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the Modern Forms Adaptive Learning switch."""
        await self.coordinator.modern_forms.adaptive_learning(adaptive_learning=True)
