"""Support for Hikvision cameras."""

from typing import override

from pyhik.hikvision import VideoChannel

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HikvisionConfigEntry
from .entity import HikvisionEntity

PARALLEL_UPDATES = 0
RTSP_PORT = 554

STREAM_TYPE_MAIN = 1
STREAM_TYPE_SUB = 2


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hikvision cameras from a config entry."""
    data = entry.runtime_data

    if data.channels:
        # NVR with video channels from get_video_channels()
        channels = [channel for channel in data.channels.values() if channel.enabled]
    else:
        # Single camera - create a default VideoChannel
        channels = [VideoChannel(id=1, name=data.device_name, enabled=True)]

    entities: list[HikvisionCamera] = []
    for channel in channels:
        entities.append(HikvisionCamera(hass, entry, channel))
        # Disabled by default: not every channel has a substream
        entities.append(
            HikvisionCamera(hass, entry, channel, stream_type=STREAM_TYPE_SUB)
        )
    async_add_entities(entities)


class HikvisionCamera(HikvisionEntity, Camera):
    """Representation of a Hikvision camera."""

    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HikvisionConfigEntry,
        channel: VideoChannel,
        stream_type: int = STREAM_TYPE_MAIN,
    ) -> None:
        """Initialize the camera."""
        super().__init__(hass, entry, channel.id)
        self._video_channel = channel
        self._stream_type = stream_type
        if stream_type == STREAM_TYPE_MAIN:
            # The main stream is named after its device
            self._attr_name = None

        # Build unique ID (unique per platform per integration)
        self._attr_unique_id = f"{self._data.device_id}_{channel.id}"

        # No pyhik event is routed here; the registration exists so the
        # camera is told when the event stream connects or drops.
        self._callback_id = f"{self._data.stream_id}.camera.{channel.id}"

        if stream_type == STREAM_TYPE_SUB:
            self._attr_translation_key = "substream"
            self._attr_entity_registry_enabled_default = False
            self._attr_unique_id += "_substream"
            self._callback_id += ".substream"

    @override
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

    @override
    async def stream_source(self) -> str | None:
        """Return the stream source URL."""
        return self._camera.get_stream_url(self._channel, stream_type=self._stream_type)
