"""Identify button for SteamVR Base Station."""

from typing import override

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SteamVRBaseStationConfigEntry
from .entity import SteamVRBaseStationEntity

# Commands to one station are serialized by the library.
PARALLEL_UPDATES = 0

IDENTIFY = ButtonEntityDescription(
    key="identify",
    device_class=ButtonDeviceClass.IDENTIFY,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SteamVRBaseStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the identify button."""
    async_add_entities([SteamVRBaseStationButton(entry.runtime_data, IDENTIFY)])


class SteamVRBaseStationButton(SteamVRBaseStationEntity, ButtonEntity):
    """Blinks the station's LED."""

    @override
    async def async_press(self) -> None:
        """Blink the LED."""
        await self.coordinator.async_identify()
