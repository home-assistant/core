"""Support for Hikvision cameras."""

import asyncio
from typing import override

from pyhik.hikvision import HikCamera, VideoChannel

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.async_ import wait_shared_future

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
        snapshot = _SharedSnapshot(hass, data.camera, channel.id)
        entities.append(HikvisionCamera(hass, entry, channel, snapshot))
        # Disabled by default: not every channel has a substream
        entities.append(
            HikvisionCamera(hass, entry, channel, snapshot, stream_type=STREAM_TYPE_SUB)
        )
    async_add_entities(entities)


class _SharedSnapshot:
    """The snapshot of a channel, shared by its main stream and substream cameras.

    pyHik takes the picture from the main stream for both. The device refuses a
    second picture request while it answers one, with a 503: a request that comes
    while one is sent waits for it, and gets the same picture.
    """

    def __init__(self, hass: HomeAssistant, camera: HikCamera, channel: int) -> None:
        """Initialize the snapshot of a channel."""
        self._hass = hass
        self._camera = camera
        self._channel = channel
        self._pending: asyncio.Future[bytes | None] | None = None

    async def async_get(self) -> bytes | None:
        """Return a picture, from the request being sent if there is one."""
        pending = self._pending
        # A request that ended is not reused, even before _ended has run: its
        # picture, or its error, is from before this call.
        if pending is None or pending.done():
            pending = self._pending = self._hass.async_add_executor_job(
                self._camera.get_snapshot, self._channel
            )
            pending.add_done_callback(self._ended)
        # Not awaited directly: a caller that is cancelled leaves the request to the
        # others, and an error no caller is left for is not reported.
        return await wait_shared_future(pending)

    def _ended(self, pending: asyncio.Future[bytes | None]) -> None:
        """Let the next request be sent."""
        if self._pending is pending:
            # Not one started since.
            self._pending = None
        if not pending.cancelled():
            # Retrieved, also when every caller was cancelled.
            pending.exception()


class HikvisionCamera(HikvisionEntity, Camera):
    """Representation of a Hikvision camera."""

    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HikvisionConfigEntry,
        channel: VideoChannel,
        snapshot: _SharedSnapshot,
        stream_type: int = STREAM_TYPE_MAIN,
    ) -> None:
        """Initialize the camera."""
        super().__init__(hass, entry, channel.id)
        self._video_channel = channel
        self._snapshot = snapshot
        self._stream_type = stream_type
        if stream_type == STREAM_TYPE_MAIN:
            # The main stream is named after its device
            self._attr_name = None

        # Build unique ID (unique per platform per integration)
        self._attr_unique_id = f"{self._data.device_id}_{channel.id}"

        # No pyhik event is routed here; the registration exists so the
        # camera is told when the event stream connects or drops.
        self._callback_id = f"{self._data.device_id}.camera.{channel.id}"

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
            return await self._snapshot.async_get()
        except Exception as err:
            raise HomeAssistantError(
                f"Error getting image from {self._video_channel.name}: {err}"
            ) from err

    @override
    async def stream_source(self) -> str | None:
        """Return the stream source URL."""
        return self._camera.get_stream_url(self._channel, stream_type=self._stream_type)
