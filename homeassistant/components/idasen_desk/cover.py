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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DeskData, IdasenDeskCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the cover platform for Idasen Desk."""
    data: DeskData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [IdasenDeskCover(data.address, data.device_info, data.coordinator)]
    )


class IdasenDeskCover(CoordinatorEntity[IdasenDeskCoordinator], CoverEntity):
    """Representation of Idasen Desk device."""

    _attr_device_class = CoverDeviceClass.DAMPER
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "desk"

    def __init__(
        self,
        address: str,
        device_info: DeviceInfo,
        coordinator: IdasenDeskCoordinator,
    ) -> None:
        """Initialize an Idasen Desk cover."""
        super().__init__(coordinator)
        self._desk = coordinator.desk
        self._attr_unique_id = address
        self._attr_device_info = device_info

        self._attr_current_cover_position = self._desk.height_percent

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._desk.is_connected is True

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

    @callback
    def _handle_coordinator_update(self, *args: Any) -> None:
        """Handle data update."""
        self._attr_current_cover_position = self._desk.height_percent
        self.async_write_ha_state()
