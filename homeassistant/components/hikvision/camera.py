"""Support for Hikvision cameras."""

from __future__ import annotations

from urllib.parse import quote

from pyhik.hikvision import VideoChannel

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HikvisionConfigEntry
from .entity import HikvisionEntity

PARALLEL_UPDATES = 0
RTSP_PORT = 554


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


class HikvisionCamera(HikvisionEntity, Camera):
    """Representation of a Hikvision camera."""

    _attr_name = None
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        entry: HikvisionConfigEntry,
        channel: VideoChannel,
    ) -> None:
        """Initialize the camera."""
        super().__init__(entry, channel.id)
        self._video_channel = channel

        # Build unique ID (unique per platform per integration)
        self._attr_unique_id = f"{self._data.device_id}_{channel.id}"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image from the camera."""
        try:
            return await self.hass.async_add_executor_job(
                self._camera.get_snapshot, self._video_channel.id
            )
        except Exception as err:
            raise HomeAssistantError(
                f"Error getting image from {self._video_channel.name}: {err}"
            ) from err

    async def stream_source(self) -> str | None:
        """Return the stream source URL.

        Constructs the RTSP URL directly to work around a bug in pyhik
        where the library includes the HTTP protocol in the RTSP URL.
        """
        # NVR uses channel * 100 + stream_type format
        # Standalone cameras use stream_type directly (1 for main stream)
        if self._data.device_type == "NVR":
            stream_channel = self._video_channel.id * 100 + 1
        else:
            stream_channel = 1

        # URL encode credentials for safety
        encoded_user = quote(self._data.username, safe="")
        encoded_pwd = quote(self._data.password, safe="")

        return (
            f"rtsp://{encoded_user}:{encoded_pwd}@"
            f"{self._data.host}:{RTSP_PORT}/Streaming/Channels/{stream_channel}"
        )
