"""This component provides support to the Ring Door Bell camera."""
import asyncio
from datetime import timedelta
from itertools import chain
import logging

from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import IMAGE_JPEG, ImageFrame
import requests

from homeassistant.components.camera import Camera
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.util import dt as dt_util

from . import ATTRIBUTION, DOMAIN
from .entity import RingEntityMixin

FORCE_REFRESH_INTERVAL = timedelta(minutes=45)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a Ring Door Bell and StickUp Camera."""
    devices = hass.data[DOMAIN][config_entry.entry_id]["devices"]

    cams = []
    for camera in chain(
        devices["doorbots"], devices["authorized_doorbots"], devices["stickup_cams"]
    ):
        if not camera.has_subscription:
            continue

        cams.append(RingCam(config_entry.entry_id, hass.data[DATA_FFMPEG], camera))

    async_add_entities(cams)


class RingCam(RingEntityMixin, Camera):
    """An implementation of a Ring Door Bell camera."""

    def __init__(self, config_entry_id, ffmpeg, device):
        """Initialize a Ring Door Bell camera."""
        super().__init__(config_entry_id, device)

        self._name = self._device.name
        self._ffmpeg = ffmpeg
        self._last_event = None
        self._last_video_id = None
        self._video_url = None
        self._expires_at = dt_util.utcnow() - FORCE_REFRESH_INTERVAL

    async def async_added_to_hass(self):
        """Register callbacks."""
        await super().async_added_to_hass()

        await self.ring_objects["history_data"].async_track_device(
            self._device, self._history_update_callback
        )

    async def async_will_remove_from_hass(self):
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
            self._expires_at = dt_util.utcnow()
            self.async_write_ha_state()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._device.id

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "video_url": self._video_url,
            "last_video_id": self._last_video_id,
        }

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        ffmpeg = ImageFrame(self._ffmpeg.binary, loop=self.hass.loop)

        if self._video_url is None:
            return

        image = await asyncio.shield(
            ffmpeg.get_image(self._video_url, output_format=IMAGE_JPEG,)
        )
        return image

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        if self._video_url is None:
            return

        stream = CameraMjpeg(self._ffmpeg.binary, loop=self.hass.loop)
        await stream.open_camera(self._video_url)

        try:
            stream_reader = await stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                stream_reader,
                self._ffmpeg.ffmpeg_stream_content_type,
            )
        finally:
            await stream.close()

    async def async_update(self):
        """Update camera entity and refresh attributes."""
        if self._last_event is None:
            return

        if self._last_event["recording"]["status"] != "ready":
            return

        utcnow = dt_util.utcnow()
        if self._last_video_id == self._last_event["id"] and utcnow <= self._expires_at:
            return

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
