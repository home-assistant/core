"""This component provides support to the Ring Door Bell camera."""
import asyncio
from datetime import timedelta
import logging

from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import IMAGE_JPEG, ImageFrame

from homeassistant.components.camera import Camera
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util

from . import (
    ATTRIBUTION,
    DATA_RING_DOORBELLS,
    DATA_RING_STICKUP_CAMS,
    SIGNAL_UPDATE_RING,
)

FORCE_REFRESH_INTERVAL = timedelta(minutes=45)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a Ring Door Bell and StickUp Camera."""
    ring_doorbell = hass.data[DATA_RING_DOORBELLS]
    ring_stickup_cams = hass.data[DATA_RING_STICKUP_CAMS]

    cams = []
    for camera in ring_doorbell + ring_stickup_cams:
        if not camera.has_subscription:
            continue

        camera = await hass.async_add_executor_job(RingCam, hass, camera)
        cams.append(camera)

    async_add_entities(cams, True)


class RingCam(Camera):
    """An implementation of a Ring Door Bell camera."""

    def __init__(self, hass, camera):
        """Initialize a Ring Door Bell camera."""
        super().__init__()
        self._camera = camera
        self._hass = hass
        self._name = self._camera.name
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._last_video_id = self._camera.last_recording_id
        self._video_url = self._camera.recording_url(self._last_video_id)
        self._utcnow = dt_util.utcnow()
        self._expires_at = FORCE_REFRESH_INTERVAL + self._utcnow
        self._disp_disconnect = None

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._disp_disconnect = async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_RING, self._update_callback
        )

    async def async_will_remove_from_hass(self):
        """Disconnect callbacks."""
        if self._disp_disconnect:
            self._disp_disconnect()
            self._disp_disconnect = None

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)
        _LOGGER.debug("Updating Ring camera %s (callback)", self.name)

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._camera.id

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "device_id": self._camera.id,
            "firmware": self._camera.firmware,
            "kind": self._camera.kind,
            "timezone": self._camera.timezone,
            "type": self._camera.family,
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

    @property
    def should_poll(self):
        """Return False, updates are controlled via the hub."""
        return False

    def update(self):
        """Update camera entity and refresh attributes."""
        _LOGGER.debug("Checking if Ring DoorBell needs to refresh video_url")

        self._utcnow = dt_util.utcnow()

        try:
            last_event = self._camera.history(limit=1)[0]
        except (IndexError, TypeError):
            return

        last_recording_id = last_event["id"]
        video_status = last_event["recording"]["status"]

        if video_status == "ready" and (
            self._last_video_id != last_recording_id or self._utcnow >= self._expires_at
        ):

            video_url = self._camera.recording_url(last_recording_id)
            if video_url:
                _LOGGER.info("Ring DoorBell properties refreshed")

                # update attributes if new video or if URL has expired
                self._last_video_id = last_recording_id
                self._video_url = video_url
                self._expires_at = FORCE_REFRESH_INTERVAL + self._utcnow
