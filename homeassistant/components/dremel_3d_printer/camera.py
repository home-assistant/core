"""Support for Dremel 3D45 Camera."""
from __future__ import annotations

from homeassistant.components.mjpeg import MjpegCamera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Dremel3DPrinterDataUpdateCoordinator, Dremel3DPrinterDeviceEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a MJPEG IP Camera for the 3D45 Model. The 3D20 and 3D40 models don't have builtin cameras."""
    coordinator: Dremel3DPrinterDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    if coordinator.api.get_model() == "3D45":
        async_add_entities([Dremel3D45Camera(coordinator, config_entry)])


class Dremel3D45Camera(Dremel3DPrinterDeviceEntity, MjpegCamera):
    """Dremel 3D45 Camera."""

    def __init__(
        self,
        coordinator: Dremel3DPrinterDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize a new Dremel 3D Printer integration camera for the 3D45 model."""
        Dremel3DPrinterDeviceEntity.__init__(
            self,
            coordinator,
            config_entry,
        )
        MjpegCamera.__init__(
            self,
            name=coordinator.api.get_title(),
            mjpeg_url=coordinator.api.get_stream_url(),
            still_image_url=coordinator.api.get_snapshot_url(),
        )
        self._attr_name = f"Dremel {self.coordinator.api.get_model()} Camera"
        self._attr_unique_id = f"camera-{config_entry.unique_id}"
