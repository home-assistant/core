"""Camera for the Trafikverket Camera integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LOCATION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_DESCRIPTION, ATTR_TYPE, DOMAIN
from .coordinator import TVDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Trafikverket Camera."""

    coordinator: TVDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            TVCamera(
                coordinator,
                entry.title,
                entry.entry_id,
            )
        ],
    )


class TVCamera(CoordinatorEntity[TVDataUpdateCoordinator], Camera):
    """Implement Trafikverket camera."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "tv_camera"
    coordinator: TVDataUpdateCoordinator

    def __init__(
        self,
        coordinator: TVDataUpdateCoordinator,
        name: str,
        entry_id: str,
    ) -> None:
        """Initialize the camera."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self._attr_unique_id = entry_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Trafikverket",
            model="v1.0",
            name=name,
            configuration_url="https://api.trafikinfo.trafikverket.se/",
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return camera picture."""
        return self.coordinator.data.image

    @property
    def is_on(self) -> bool:
        """Return camera on."""
        return self.coordinator.data.data.active is True

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional attributes."""
        return {
            ATTR_DESCRIPTION: self.coordinator.data.data.description,
            ATTR_LOCATION: self.coordinator.data.data.location,
            ATTR_TYPE: self.coordinator.data.data.camera_type,
        }
