"""Cover Entity for Genie Garage Door."""

from __future__ import annotations

from typing import Any

import aiohttp

from homeassistant.components.cover import CoverDeviceClass, CoverEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SUPPORTED_FEATURES
from .coordinator import AladdinConnectConfigEntry, AladdinConnectCoordinator
from .entity import AladdinConnectEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AladdinConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the cover platform."""
    coordinators = entry.runtime_data

    async_add_entities(
        AladdinCoverEntity(coordinator) for coordinator in coordinators.values()
    )


class AladdinCoverEntity(AladdinConnectEntity, CoverEntity):
    """Representation of Aladdin Connect cover."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_supported_features = SUPPORTED_FEATURES
    _attr_name = None

    def __init__(self, coordinator: AladdinConnectCoordinator) -> None:
        """Initialize the Aladdin Connect cover."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.data.unique_id

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Issue open command to cover."""
        try:
            await self.client.open_door(self._device_id, self._number)
        except aiohttp.ClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="open_door_failed",
            ) from err

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Issue close command to cover."""
        try:
            await self.client.close_door(self._device_id, self._number)
        except aiohttp.ClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="close_door_failed",
            ) from err

    @property
    def is_closed(self) -> bool | None:
        """Update is closed attribute."""
        if (status := self.coordinator.data.status) is None:
            return None
        return status == "closed"

    @property
    def is_closing(self) -> bool | None:
        """Update is closing attribute."""
        return self.coordinator.data.status == "closing"

    @property
    def is_opening(self) -> bool | None:
        """Update is opening attribute."""
        return self.coordinator.data.status == "opening"
