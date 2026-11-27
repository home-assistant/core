"""Support for Yardian buttons."""

import asyncio
from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BUTTON_REFRESH_DELAY
from .coordinator import YardianConfigEntry, YardianUpdateCoordinator
from .entity import YardianEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YardianConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Yardian button platform."""
    coordinator = entry.runtime_data

    async_add_entities([YardianStopButton(coordinator)])


class YardianStopButton(YardianEntity, ButtonEntity):
    """Representation of a Yardian Stop All Irrigation button."""

    _attr_translation_key = "stop_irrigation"

    def __init__(self, coordinator: YardianUpdateCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.client = coordinator.controller

        self._attr_unique_id = f"{coordinator.yid}_stop_all"

    @override
    async def async_press(self) -> None:
        """Handle the button press."""
        await self.client.stop_irrigation()

        await asyncio.sleep(BUTTON_REFRESH_DELAY)
        await self.coordinator.async_request_refresh()
