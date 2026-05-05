"""Cover platform for Fluss+ devices with a position sensor."""

from __future__ import annotations

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
from .entity import FlussEntity, has_open_close_sensor

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlussConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up cover entities for devices reporting an open/close sensor."""
    coordinator = entry.runtime_data
    async_add_entities(
        FlussCover(coordinator, device)
        for device in coordinator.data.values()
        if has_open_close_sensor(device)
    )


class FlussCover(FlussEntity, CoverEntity):
    """Representation of a Fluss+ cover (garage door / gate)."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    _attr_name = None

    @property
    def is_closed(self) -> bool | None:
        """Return whether the cover is closed."""
        status = self.device.open_close_status
        if isinstance(status, bool):
            return not status
        if isinstance(status, str):
            normalized = status.lower()
            if normalized == "closed":
                return True
            if normalized == "open":
                return False
        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        try:
            await self.coordinator.api.async_open_device(self.device_id)
        except FlussApiClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="open_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        try:
            await self.coordinator.api.async_close_device(self.device_id)
        except FlussApiClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="close_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()
