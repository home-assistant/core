"""Support for Fluss cover devices (gates and doors)."""

from __future__ import annotations

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
from homeassistant.helpers.event import async_call_later

from .coordinator import (
    FlussConfigEntry,
    FlussDataUpdateCoordinator,
    device_has_cover_status,
)
from .entity import FlussEntity

PARALLEL_UPDATES = 1

# Wait before polling status so the device has time to reflect the new state.
STATUS_REFRESH_DELAY = 10


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
        device: dict[str, Any],
    ) -> None:
        """Initialize the cover entity."""
        super().__init__(coordinator, device_id, device, unique_id_suffix="cover")

    @property
    def icon(self) -> str:
        """Return the icon based on configured icon type and current state."""
        if self.is_closed is False:
            return self._open_icon
        return self._base_icon

    @property
    def is_closed(self) -> bool | None:
        """Return true if the cover is closed."""
        status = self.device.get("status") or {}
        open_close = status.get("openCloseStatus")
        if open_close == "Closed":
            return True
        if open_close == "Open":
            return False
        return None

    async def _async_schedule_refresh(self) -> None:
        """Schedule a delayed refresh so the device state catches up."""

        async def _refresh(_now: Any) -> None:
            await self.coordinator.async_request_refresh()

        async_call_later(self.hass, STATUS_REFRESH_DELAY, _refresh)

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
        await self._async_schedule_refresh()

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
        await self._async_schedule_refresh()
