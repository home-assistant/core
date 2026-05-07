"""Cover platform for Fluss+ devices that report an open/closed status."""

from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import FlussApiClientError, FlussConfigEntry
from .entity import FlussEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlussConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fluss covers for devices that report an open/closed status."""
    coordinator = entry.runtime_data

    async_add_entities(
        FlussCover(coordinator, device_id, device)
        for device_id, device in coordinator.data.items()
        if "openCloseStatus" in device
    )


class FlussCover(FlussEntity, CoverEntity):
    """Representation of a Fluss+ cover."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_name = None
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    @property
    def available(self) -> bool:
        """Return True only when the device is online."""
        return super().available and self.device["internetConnected"]

    @property
    def is_closed(self) -> bool | None:
        """Return whether the cover is closed."""
        status = self.device.get("openCloseStatus")
        if status == "Closed":
            return True
        if status == "Open":
            return False
        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        try:
            await self.coordinator.api.async_open_device(self.device_id)
        except FlussApiClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        try:
            await self.coordinator.api.async_close_device(self.device_id)
        except FlussApiClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        await self.coordinator.async_request_refresh()
