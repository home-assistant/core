"""Platform for image integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from devolo_plc_api import wifi_qr_code
from devolo_plc_api.device_api import WifiGuestAccessGet

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import DevoloHomeNetworkConfigEntry
from .const import IMAGE_GUEST_WIFI, SWITCH_GUEST_WIFI
from .coordinator import DevoloDataUpdateCoordinator
from .entity import DevoloCoordinatorEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DevoloImageEntityDescription(ImageEntityDescription):
    """Describes devolo image entity."""

    image_func: Callable[[WifiGuestAccessGet], bytes]


IMAGE_TYPES: dict[str, DevoloImageEntityDescription] = {
    IMAGE_GUEST_WIFI: DevoloImageEntityDescription(
        key=IMAGE_GUEST_WIFI,
        entity_category=EntityCategory.DIAGNOSTIC,
        image_func=partial(wifi_qr_code, omitsize=True),
    )
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DevoloHomeNetworkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    coordinators = entry.runtime_data.coordinators

    entities: list[ImageEntity] = []
    entities.append(
        DevoloImageEntity(
            entry,
            coordinators[SWITCH_GUEST_WIFI],
            IMAGE_TYPES[IMAGE_GUEST_WIFI],
        )
    )
    async_add_entities(entities)


class DevoloImageEntity(DevoloCoordinatorEntity[WifiGuestAccessGet], ImageEntity):
    """Representation of a devolo image."""

    _attr_content_type = "image/svg+xml"

    def __init__(
        self,
        entry: DevoloHomeNetworkConfigEntry,
        coordinator: DevoloDataUpdateCoordinator[WifiGuestAccessGet],
        description: DevoloImageEntityDescription,
    ) -> None:
        """Initialize entity."""
        self.entity_description: DevoloImageEntityDescription = description
        super().__init__(entry, coordinator)
        ImageEntity.__init__(self, coordinator.hass)
        self._attr_image_last_updated = dt_util.utcnow()
        self._data = self.coordinator.data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            self._data.ssid != self.coordinator.data.ssid
            or self._data.key != self.coordinator.data.key
        ):
            self._data = self.coordinator.data
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return self.entity_description.image_func(self.coordinator.data)
