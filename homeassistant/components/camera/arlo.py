"""
This component provides basic support for Netgear Arlo IP cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.arlo/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.components.arlo import DEFAULT_BRAND, DATA_ARLO
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from homeassistant.components.ffmpeg import DATA_FFMPEG

DEPENDENCIES = ['arlo', 'ffmpeg']

_LOGGER = logging.getLogger(__name__)

CONF_FFMPEG_ARGUMENTS = 'ffmpeg_arguments'
ARLO_MODE_ARMED = 'armed'
ARLO_MODE_DISARMED = 'disarmed'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_FFMPEG_ARGUMENTS): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up an Arlo IP Camera."""
    arlo = hass.data.get(DATA_ARLO)
    if not arlo:
        return False

    cameras = []
    for camera in arlo.cameras:
        cameras.append(ArloCam(hass, camera, config))

    async_add_devices(cameras, True)


class ArloCam(Camera):
    """An implementation of a Netgear Arlo IP camera."""

    def __init__(self, hass, camera, device_info):
        """Initialize an Arlo camera."""
        super().__init__()
        self._camera = camera
        self._name = self._camera.name
        self._motion_status = False
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._ffmpeg_arguments = device_info.get(CONF_FFMPEG_ARGUMENTS)

    def camera_image(self):
        """Return a still image response from the camera."""
        return self._camera.last_image

    @asyncio.coroutine
    def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        from haffmpeg import CameraMjpeg
        video = self._camera.last_video
        if not video:
            return

        stream = CameraMjpeg(self._ffmpeg.binary, loop=self.hass.loop)
        yield from stream.open_camera(
            video.video_url, extra_cmd=self._ffmpeg_arguments)

        yield from async_aiohttp_proxy_stream(
            self.hass, request, stream,
            'multipart/x-mixed-replace;boundary=ffserver')
        yield from stream.close()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def model(self):
        """Camera model."""
        return self._camera.model_id

    @property
    def brand(self):
        """Camera brand."""
        return DEFAULT_BRAND

    @property
    def should_poll(self):
        """Camera should poll periodically."""
        return True

    @property
    def motion_detection_enabled(self):
        """Camera Motion Detection Status."""
        return self._motion_status

    def set_base_station_mode(self, mode):
        """Set the mode in the base station."""
        # Get the list of base stations identified by library
        base_stations = self.hass.data[DATA_ARLO].base_stations

        # Some Arlo cameras does not have basestation
        # So check if there is base station detected first
        # if yes, then choose the primary base station
        # Set the mode on the chosen base station
        if base_stations:
            primary_base_station = base_stations[0]
            primary_base_station.mode = mode

    def enable_motion_detection(self):
        """Enable the Motion detection in base station (Arm)."""
        self._motion_status = True
        self.set_base_station_mode(ARLO_MODE_ARMED)

    def disable_motion_detection(self):
        """Disable the motion detection in base station (Disarm)."""
        self._motion_status = False
        self.set_base_station_mode(ARLO_MODE_DISARMED)
