"""Support for Gogogate2 garage Doors."""

from __future__ import annotations

from typing import Any

from ismartgate.common import (
    AbstractDoor,
    DoorStatus,
    TransitionDoorStatus,
    get_configured_doors,
)

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import GoGoGate2Entity, cover_unique_id, get_data_update_coordinator
from .coordinator import DeviceDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the config entry."""
    data_update_coordinator = get_data_update_coordinator(hass, config_entry)

    async_add_entities(
        [
            DeviceCover(config_entry, data_update_coordinator, door)
            for door in get_configured_doors(data_update_coordinator.data)
        ]
    )


class DeviceCover(GoGoGate2Entity, CoverEntity):
    """Cover entity for gogogate2."""

    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(
        self,
        config_entry: ConfigEntry,
        data_update_coordinator: DeviceDataUpdateCoordinator,
        door: AbstractDoor,
    ) -> None:
        """Initialize the object."""
        unique_id = cover_unique_id(config_entry, door)
        super().__init__(config_entry, data_update_coordinator, door, unique_id)
        self._attr_device_class = (
            CoverDeviceClass.GATE if self.door.gate else CoverDeviceClass.GARAGE
        )

    @property
    def name(self) -> str | None:
        """Return the name of the door."""
        return self.door.name

    @property
    def is_closed(self) -> bool | None:
        """Return true if cover is closed, else False."""
        door_status = self.door_status
        if door_status == DoorStatus.OPENED:
            return False
        if door_status == DoorStatus.CLOSED:
            return True
        return None

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self.door_status == TransitionDoorStatus.CLOSING

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self.door_status == TransitionDoorStatus.OPENING

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the door."""
        await self._api.async_open_door(self._door_id)
        await self.coordinator.async_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the door."""
        await self._api.async_close_door(self._door_id)
        await self.coordinator.async_refresh()
