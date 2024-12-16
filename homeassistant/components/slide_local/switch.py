"""Support for Slide button."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SlideConfigEntry
from .coordinator import SlideCoordinator
from .entity import SlideEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SlideConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch for Slide platform."""

    coordinator = entry.runtime_data

    async_add_entities([SlideSwitch(coordinator)])


class SlideSwitch(SlideEntity, SwitchEntity):
    """Defines a Slide switch."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "touchgo"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, coordinator: SlideCoordinator) -> None:
        """Initialize the slide switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.data["mac"]}-touchgo"

    @property
    def is_on(self) -> bool:
        """Return if switch is on."""
        return self.coordinator.data["touch_go"]

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off touchgo."""
        await self.coordinator.slide.slide_set_touchgo(self.coordinator.host, False)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on touchgo."""
        await self.coordinator.slide.slide_set_touchgo(self.coordinator.host, True)
        await self.coordinator.async_request_refresh()
