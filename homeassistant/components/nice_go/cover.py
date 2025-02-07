"""Cover entity for Nice G.O."""

from typing import Any

from aiohttp import ClientError
from nice_go import ApiError

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NiceGOConfigEntry
from .const import DOMAIN
from .entity import NiceGOEntity

DEVICE_CLASSES = {
    "WallStation": CoverDeviceClass.GARAGE,
    "Mms100": CoverDeviceClass.GATE,
    "WallStation_ESP32": CoverDeviceClass.GARAGE,
}
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NiceGOConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nice G.O. cover."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        NiceGOCoverEntity(coordinator, device_id, device_data.name)
        for device_id, device_data in coordinator.data.items()
    )


class NiceGOCoverEntity(NiceGOEntity, CoverEntity):
    """Representation of a Nice G.O. cover."""

    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    _attr_name = None

    @property
    def device_class(self) -> CoverDeviceClass:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASSES.get(self.data.type, CoverDeviceClass.GARAGE)

    @property
    def is_closed(self) -> bool:
        """Return if cover is closed."""
        return self.data.barrier_status == "closed"

    @property
    def is_opened(self) -> bool:
        """Return if cover is open."""
        return self.data.barrier_status == "open"

    @property
    def is_opening(self) -> bool:
        """Return if cover is opening."""
        return self.data.barrier_status == "opening"

    @property
    def is_closing(self) -> bool:
        """Return if cover is closing."""
        return self.data.barrier_status == "closing"

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the garage door."""
        if self.is_closed:
            return

        try:
            await self.coordinator.api.close_barrier(self._device_id)
        except (ApiError, ClientError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="close_cover_error",
                translation_placeholders={"exception": str(err)},
            ) from err

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the garage door."""
        if self.is_opened:
            return

        try:
            await self.coordinator.api.open_barrier(self._device_id)
        except (ApiError, ClientError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="open_cover_error",
                translation_placeholders={"exception": str(err)},
            ) from err
