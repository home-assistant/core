"""Slideshow switch for Immich Frames."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ImmichFramesConfigEntry, ImmichFramesDataUpdateCoordinator
from .entity import ImmichFramesEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImmichFramesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the slideshow switch."""
    async_add_entities([SlideshowSwitch(entry.runtime_data)])


class SlideshowSwitch(ImmichFramesEntity, SwitchEntity):
    """Pause or resume automatic photo rotation."""

    def __init__(self, coordinator: ImmichFramesDataUpdateCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, "slideshow")

    @property
    @override
    def is_on(self) -> bool:
        """Return whether automatic rotation is enabled."""
        return not self.coordinator.paused

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Resume automatic rotation."""
        self.coordinator.paused = False
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Pause automatic rotation."""
        self.coordinator.paused = True
        self.async_write_ha_state()
