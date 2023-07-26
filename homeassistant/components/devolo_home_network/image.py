"""Platform for image integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from devolo_plc_api import Device, wifi_qr_code
from devolo_plc_api.device_api import WifiGuestAccessGet

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import homeassistant.util.dt as dt_util

from .const import DOMAIN, IMAGE_GUEST_WIFI, SWITCH_GUEST_WIFI
from .entity import DevoloCoordinatorEntity

QR_CODE_SCALE = 4


@dataclass
class DevoloImageRequiredKeysMixin:
    """Mixin for required keys."""

    image_func: Callable[[WifiGuestAccessGet], bytes]


@dataclass
class DevoloImageEntityDescription(
    ImageEntityDescription, DevoloImageRequiredKeysMixin
):
    """Describes devolo image entity."""


IMAGE_TYPES: dict[str, DevoloImageEntityDescription] = {
    IMAGE_GUEST_WIFI: DevoloImageEntityDescription(
        key=IMAGE_GUEST_WIFI,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        image_func=partial(wifi_qr_code, scale=QR_CODE_SCALE),
    )
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    device: Device = hass.data[DOMAIN][entry.entry_id]["device"]
    coordinators: dict[str, DataUpdateCoordinator[Any]] = hass.data[DOMAIN][
        entry.entry_id
    ]["coordinators"]

    entities: list[ImageEntity] = []
    entities.append(
        DevoloImageEntity(
            entry,
            coordinators[SWITCH_GUEST_WIFI],
            IMAGE_TYPES[IMAGE_GUEST_WIFI],
            device,
        )
    )
    async_add_entities(entities)


class DevoloImageEntity(DevoloCoordinatorEntity[WifiGuestAccessGet], ImageEntity):
    """Representation of a devolo image."""

    _attr_content_type = "image/svg+xml"
    _data: WifiGuestAccessGet | None = None

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator[WifiGuestAccessGet],
        description: DevoloImageEntityDescription,
        device: Device,
    ) -> None:
        """Initialize entity."""
        self.entity_description: DevoloImageEntityDescription = description
        super().__init__(entry, coordinator, device)
        ImageEntity.__init__(self, coordinator.hass)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._data != self.coordinator.data:
            self._data = self.coordinator.data
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return self.entity_description.image_func(self.coordinator.data)
