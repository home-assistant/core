"""
This component provides support to the Ring Door Bell camera.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.ring/
"""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import ATTR_ATTRIBUTION, CONF_SCAN_INTERVAL
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.util import dt as dt_util

from . import ATTRIBUTION, DATA_RING, NOTIFICATION_ID

CONF_FFMPEG_ARGUMENTS = 'ffmpeg_arguments'

DEPENDENCIES = ['ring', 'ffmpeg']

FORCE_REFRESH_INTERVAL = timedelta(minutes=45)

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_TITLE = 'Ring Camera Setup'

SCAN_INTERVAL = timedelta(seconds=90)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_FFMPEG_ARGUMENTS): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a Ring Door Bell and StickUp Camera."""
    ring = hass.data[DATA_RING]

    cams = []
    cams_no_plan = []
    for camera in ring.doorbells:
        if camera.has_subscription:
            cams.append(RingCam(hass, camera, config))
        else:
            cams_no_plan.append(camera)

    for camera in ring.stickup_cams:
        if camera.has_subscription:
            cams.append(RingCam(hass, camera, config))
        else:
            cams_no_plan.append(camera)

    # show notification for all cameras without an active subscription
    if cams_no_plan:
        cameras = str(', '.join([camera.name for camera in cams_no_plan]))

        err_msg = '''A Ring Protect Plan is required for the''' \
                  ''' following cameras: {}.'''.format(cameras)

        _LOGGER.error(err_msg)
        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(err_msg),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)

    add_entities(cams, True)
    return True


class RingCam(Camera):
    """An implementation of a Ring Door Bell camera."""

    def __init__(self, hass, camera, device_info):
        """Initialize a Ring Door Bell camera."""
        super(RingCam, self).__init__()
        self._camera = camera
        self._hass = hass
        self._name = self._camera.name
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._ffmpeg_arguments = device_info.get(CONF_FFMPEG_ARGUMENTS)
        self._last_video_id = self._camera.last_recording_id
        self._video_url = self._camera.recording_url(self._last_video_id)
        self._utcnow = dt_util.utcnow()
        self._expires_at = FORCE_REFRESH_INTERVAL + self._utcnow

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
            'device_id': self._camera.id,
            'firmware': self._camera.firmware,
            'kind': self._camera.kind,
            'timezone': self._camera.timezone,
            'type': self._camera.family,
            'video_url': self._video_url,
        }

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        from haffmpeg.tools import ImageFrame, IMAGE_JPEG
        ffmpeg = ImageFrame(self._ffmpeg.binary, loop=self.hass.loop)

        if self._video_url is None:
            return

        image = await asyncio.shield(ffmpeg.get_image(
            self._video_url, output_format=IMAGE_JPEG,
            extra_cmd=self._ffmpeg_arguments), loop=self.hass.loop)
        return image

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        from haffmpeg.camera import CameraMjpeg

        if self._video_url is None:
            return

        stream = CameraMjpeg(self._ffmpeg.binary, loop=self.hass.loop)
        await stream.open_camera(
            self._video_url, extra_cmd=self._ffmpeg_arguments)

        try:
            stream_reader = await stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass, request, stream_reader,
                self._ffmpeg.ffmpeg_stream_content_type)
        finally:
            await stream.close()

    @property
    def should_poll(self):
        """Update the image periodically."""
        return True

    def update(self):
        """Update camera entity and refresh attributes."""
        _LOGGER.debug("Checking if Ring DoorBell needs to refresh video_url")

        self._camera.update()
        self._utcnow = dt_util.utcnow()

        last_recording_id = self._camera.last_recording_id

        if self._last_video_id != last_recording_id or \
           self._utcnow >= self._expires_at:

            _LOGGER.info("Ring DoorBell properties refreshed")

            # update attributes if new video or if URL has expired
            self._last_video_id = self._camera.last_recording_id
            self._video_url = self._camera.recording_url(self._last_video_id)
            self._expires_at = FORCE_REFRESH_INTERVAL + self._utcnow
