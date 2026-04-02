"""Support for Fluss cover devices (gates and doors)."""

from __future__ import annotations

from typing import Any

from fluss_api import FlussApiClientError

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FlussDataUpdateCoordinator
from .entity import FlussEntity

type FlussConfigEntry = ConfigEntry[FlussDataUpdateCoordinator]

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlussConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fluss cover entities from a config entry."""
    coordinator = entry.runtime_data
    devices = coordinator.data

    async_add_entities(
        FlussCover(coordinator, device_id, device)
        for device_id, device in devices.items()
    )


class FlussCover(FlussEntity, CoverEntity):
    """Representation of a Fluss gate/door as a cover."""

    _attr_device_class = CoverDeviceClass.GATE
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
    def is_closed(self) -> bool | None:
        """Return true if the cover is closed."""
        status = self.device.get("status")
        if status is None:
            return None
        return status.get("state") == "closed"

    @property
    def is_opening(self) -> bool | None:
        """Return true if the cover is opening."""
        status = self.device.get("status")
        if status is None:
            return None
        return status.get("state") == "opening"

    @property
    def is_closing(self) -> bool | None:
        """Return true if the cover is closing."""
        status = self.device.get("status")
        if status is None:
            return None
        return status.get("state") == "closing"

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
        await self.coordinator.async_request_refresh()

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
        await self.coordinator.async_request_refresh()
