"""Support for Fluss cover devices (gates and doors)."""

from __future__ import annotations

import asyncio
from typing import Any

from fluss_api import FlussApiClientError

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    FlussConfigEntry,
    FlussDataUpdateCoordinator,
    device_has_cover_status,
)
from .entity import FlussEntity

PARALLEL_UPDATES = 1

STATUS_REFRESH_DELAY = 10  # seconds to wait before polling status after open/close


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlussConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fluss cover entities for devices with open/close status."""
    coordinator = entry.runtime_data

    async_add_entities(
        FlussCover(coordinator, device_id, device)
        for device_id, device in coordinator.data.items()
        if device_has_cover_status(device)
    )


class FlussCover(FlussEntity, CoverEntity):
    """Representation of a Fluss gate/door as a cover."""

    _attr_device_class = CoverDeviceClass.DOOR
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    _attr_name = None

    def __init__(
        self,
        coordinator: FlussDataUpdateCoordinator,
        device_id: str,
        device: dict,
    ) -> None:
        """Initialize the cover entity."""
        super().__init__(coordinator, device_id, device, unique_id_suffix="cover")

    @property
    def icon(self) -> str:
        """Return the icon based on configured icon type and current state."""
        if self.is_opening or self.is_closing:
            return self._alert_icon
        if self.is_closed is False:
            return self._open_icon
        if self.is_closed is None:
            return self._base_icon
        return self._base_icon

    @property
    def is_closed(self) -> bool | None:
        """Return true if the cover is closed."""
        status = self.device.get("status")
        if status is None:
            return None
        open_close = status.get("openCloseStatus")
        if open_close == "Closed":
            return True
        if open_close == "Open":
            return False
        return None

    async def _async_delayed_refresh(self) -> None:
        """Wait then refresh coordinator to pick up new status."""
        await asyncio.sleep(STATUS_REFRESH_DELAY)
        await self.coordinator.async_request_refresh()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the gate/door."""
        try:
            await self.coordinator.api.async_open_device(self.device_id)
        except FlussApiClientError as err:
            raise HomeAssistantError(
                translation_domain="fluss",
                translation_key="open_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self.hass.async_create_task(self._async_delayed_refresh())

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the gate/door."""
        try:
            await self.coordinator.api.async_close_device(self.device_id)
        except FlussApiClientError as err:
            raise HomeAssistantError(
                translation_domain="fluss",
                translation_key="close_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self.hass.async_create_task(self._async_delayed_refresh())
