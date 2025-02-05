"""Idasen Desk integration cover platform."""

from __future__ import annotations

from typing import Any

from bleak.exc import BleakError

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IdasenDeskConfigEntry, IdasenDeskCoordinator
from .entity import IdasenDeskEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IdasenDeskConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the cover platform for Idasen Desk."""
    coordinator = entry.runtime_data
    async_add_entities([IdasenDeskCover(coordinator)])


class IdasenDeskCover(IdasenDeskEntity, CoverEntity):
    """Representation of Idasen Desk device."""

    _attr_device_class = CoverDeviceClass.DAMPER
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    _attr_name = None
    _attr_translation_key = "desk"

    def __init__(self, coordinator: IdasenDeskCoordinator) -> None:
        """Initialize an Idasen Desk cover."""
        super().__init__(coordinator.address, coordinator)

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        return self.current_cover_position == 0

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        try:
            await self._desk.move_down()
        except BleakError as err:
            raise HomeAssistantError("Failed to move down: Bluetooth error") from err

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        try:
            await self._desk.move_up()
        except BleakError as err:
            raise HomeAssistantError("Failed to move up: Bluetooth error") from err

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        try:
            await self._desk.stop()
        except BleakError as err:
            raise HomeAssistantError("Failed to stop moving: Bluetooth error") from err

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover shutter to a specific position."""
        try:
            await self._desk.move_to(int(kwargs[ATTR_POSITION]))
        except BleakError as err:
            raise HomeAssistantError(
                "Failed to move to specified position: Bluetooth error"
            ) from err

    @property
    def current_cover_position(self) -> int | None:
        """Return the current cover position."""
        return self._desk.height_percent
