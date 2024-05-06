"""Component providing support to the Ring Door Bell camera."""
from __future__ import annotations

from datetime import timedelta
from itertools import chain
import logging
from typing import Optional

from haffmpeg.camera import CameraMjpeg
import requests

from homeassistant.components import ffmpeg
from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, RING_DEVICES, RING_DEVICES_COORDINATOR
from .coordinator import RingDataCoordinator
from .entity import RingEntity

FORCE_REFRESH_INTERVAL = timedelta(minutes=3)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Ring Door Bell and StickUp Camera."""
    devices = hass.data[DOMAIN][config_entry.entry_id][RING_DEVICES]
    devices_coordinator: RingDataCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        RING_DEVICES_COORDINATOR
    ]
    ffmpeg_manager = ffmpeg.get_ffmpeg_manager(hass)

    cams = []
    for camera in chain(
        devices["doorbots"], devices["authorized_doorbots"], devices["stickup_cams"]
    ):
        if not camera.has_subscription:
            continue

        cams.append(RingCam(camera, devices_coordinator, ffmpeg_manager))

    async_add_entities(cams)


class RingCam(RingEntity, Camera):
    """An implementation of a Ring Door Bell camera."""

    _attr_name = None

    def __init__(self, device, coordinator, ffmpeg_manager):
        """Initialize a Ring Door Bell camera."""
        super().__init__(device, coordinator)
        Camera.__init__(self)

        self._ffmpeg_manager = ffmpeg_manager
        self._last_event = None
        self._last_video_id = None
        self._video_url = None
        self._image = None
        self._expires_at = dt_util.utcnow() - FORCE_REFRESH_INTERVAL
        self._attr_unique_id = device.id

    @callback
    def _handle_coordinator_update(self):
        """Call update method."""
        history_data: Optional[list]
        if not (history_data := self._get_coordinator_history()):
            return
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
