"""Component providing support to the Ring Door Bell camera."""
from __future__ import annotations

from datetime import timedelta
from itertools import chain
import logging

from haffmpeg.camera import CameraMjpeg
import requests

from homeassistant.components import ffmpeg
from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import DOMAIN
from .entity import RingEntityMixin

FORCE_REFRESH_INTERVAL = timedelta(minutes=3)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Ring Door Bell and StickUp Camera."""
    devices = hass.data[DOMAIN][config_entry.entry_id]["devices"]
    ffmpeg_manager = ffmpeg.get_ffmpeg_manager(hass)

    cams = []
    for camera in chain(
        devices["doorbots"], devices["authorized_doorbots"], devices["stickup_cams"]
    ):
        if not camera.has_subscription:
            continue

        cams.append(RingCam(config_entry.entry_id, ffmpeg_manager, camera))

    async_add_entities(cams)


class RingCam(RingEntityMixin, Camera):
    """An implementation of a Ring Door Bell camera."""

    _attr_name = None

    def __init__(self, config_entry_id, ffmpeg_manager, device):
        """Initialize a Ring Door Bell camera."""
        super().__init__(config_entry_id, device)

        self._ffmpeg_manager = ffmpeg_manager
        self._last_event = None
        self._last_video_id = None
        self._video_url = None
        self._image = None
        self._expires_at = dt_util.utcnow() - FORCE_REFRESH_INTERVAL
        self._attr_unique_id = device.id

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        await self.ring_objects["history_data"].async_track_device(
            self._device, self._history_update_callback
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect callbacks."""
        await super().async_will_remove_from_hass()

        self.ring_objects["history_data"].async_untrack_device(
            self._device, self._history_update_callback
        )

    @callback
    def _history_update_callback(self, history_data):
        """Call update method."""
        if history_data:
            self._last_event = history_data[0]
            self.async_schedule_update_ha_state(True)
        else:
            self._last_event = None
            self._last_video_id = None
            self._video_url = None
            self._image = None
            self._expires_at = dt_util.utcnow()
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "video_url": self._video_url,
            "last_video_id": self._last_video_id,
        }

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        if self._image is None and self._video_url:
            image = await ffmpeg.async_get_image(
                self.hass,
                self._video_url,
                width=width,
                height=height,
            )

            if image:
                self._image = image

        return self._image

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        if self._video_url is None:
            return

        stream = CameraMjpeg(self._ffmpeg_manager.binary)
        await stream.open_camera(self._video_url)

        try:
            stream_reader = await stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                stream_reader,
                self._ffmpeg_manager.ffmpeg_stream_content_type,
            )
        finally:
            await stream.close()

    async def async_update(self) -> None:
        """Update camera entity and refresh attributes."""
        if self._last_event is None:
            return

        if self._last_event["recording"]["status"] != "ready":
            return

        utcnow = dt_util.utcnow()
        if self._last_video_id == self._last_event["id"] and utcnow <= self._expires_at:
            return

        if self._last_video_id != self._last_event["id"]:
            self._image = None

        try:
            video_url = await self.hass.async_add_executor_job(
                self._device.recording_url, self._last_event["id"]
            )
        except requests.Timeout:
            _LOGGER.warning(
                "Time out fetching recording url for camera %s", self.entity_id
            )
            video_url = None

        if video_url:
            self._last_video_id = self._last_event["id"]
            self._video_url = video_url
            self._expires_at = FORCE_REFRESH_INTERVAL + utcnow
