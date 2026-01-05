"""Support for Hikvision cameras."""

from __future__ import annotations

import logging

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HikvisionConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hikvision cameras from a config entry."""
    data = entry.runtime_data
    camera = data.camera

    # Get available channels from the library
    channels = await hass.async_add_executor_job(camera.get_channels)

    if channels:
        entities = [HikvisionCamera(entry, channel) for channel in channels]
    else:
        # Fallback to single camera if no channels detected
        entities = [HikvisionCamera(entry, 1)]

    async_add_entities(entities)


class HikvisionCamera(Camera):
    """Representation of a Hikvision camera."""

    _attr_has_entity_name = True
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        entry: HikvisionConfigEntry,
        channel: int,
    ) -> None:
        """Initialize the camera."""
        super().__init__()
        self._entry = entry
        self._data = entry.runtime_data
        self._channel = channel
        self._camera = self._data.camera

        # Build unique ID
        self._attr_unique_id = f"{self._data.device_id}_camera_{channel}"

        # Build entity name based on device type
        if self._data.device_type == "NVR":
            self._attr_name = f"Channel {channel}"
        else:
            self._attr_name = None  # Use device name

        # Device info for device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._data.device_id)},
            name=self._data.device_name,
            manufacturer="Hikvision",
            model=self._data.device_type,
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image from the camera."""
        try:
            return await self.hass.async_add_executor_job(
                self._camera.get_snapshot, self._channel
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Error getting camera image from %s channel %d: %s",
                self._data.device_name,
                self._channel,
                err,
            )
            return None

    async def stream_source(self) -> str | None:
        """Return the stream source URL."""
        return await self.hass.async_add_executor_job(
            self._camera.get_stream_url, self._channel
        )
