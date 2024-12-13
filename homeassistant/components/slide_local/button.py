"""Support for Slide covers."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SlideConfigEntry
from .coordinator import SlideCoordinator
from .entity import SlideEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SlideConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up cover(s) for Slide platform."""

    coordinator = entry.runtime_data

    async_add_entities(
        [
            SlideButton(
                coordinator,
            )
        ]
    )


class SlideButton(SlideEntity, ButtonEntity):
    """Defines a Slide button."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "calibrate"

    def __init__(
        self,
        coordinator: SlideCoordinator,
    ) -> None:
        """Initialize the ZHA binary sensor."""
        super().__init__(coordinator)

        self._attr_device_class = ButtonDeviceClass.IDENTIFY
        self._attr_unique_id = coordinator.data["mac"]

    async def async_press(self) -> None:
        """Send out a calibrate command."""
        await self.coordinator.slide.slide_calibrate(self.coordinator.host)
