"""Support for Hikvision cameras."""

from __future__ import annotations

from pyhik.hikvision import VideoChannel

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HikvisionConfigEntry
from .const import DOMAIN

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hikvision cameras from a config entry."""
    data = entry.runtime_data

    if data.channels:
        # NVR with video channels from get_video_channels()
        async_add_entities(
            HikvisionCamera(entry, channel)
            for channel in data.channels.values()
            if channel.enabled
        )
    else:
        # Single camera - create a default VideoChannel
        async_add_entities(
            [
                HikvisionCamera(
                    entry,
                    VideoChannel(id=1, name=data.device_name, enabled=True),
                )
            ]
        )


class HikvisionCamera(Camera):
    """Representation of a Hikvision camera."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        entry: HikvisionConfigEntry,
        channel: VideoChannel,
    ) -> None:
        """Initialize the camera."""
        super().__init__()
        self._data = entry.runtime_data
        self._channel = channel
        self._camera = self._data.camera

        # Build unique ID (unique per platform per integration)
        self._attr_unique_id = f"{self._data.device_id}_{channel.id}"

        # Device info for device registry
        if self._data.device_type == "NVR":
            # NVR channels get their own device linked to the NVR via via_device
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{self._data.device_id}_{channel.id}")},
                via_device=(DOMAIN, self._data.device_id),
                name=channel.name,
                manufacturer="Hikvision",
                model="NVR channel",
            )
        else:
            # Single camera device
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
                self._camera.get_snapshot, self._channel.id
            )
        except Exception as err:
            raise HomeAssistantError(
                f"Error getting image from {self._channel.name}: {err}"
            ) from err

    async def stream_source(self) -> str | None:
        """Return the stream source URL."""
        return self._camera.get_stream_url(self._channel.id)
