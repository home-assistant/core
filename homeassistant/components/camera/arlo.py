"""
Support for Netgear Arlo IP cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.arlo/
"""
import logging

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.components.arlo import (
    DEFAULT_BRAND, DATA_ARLO, SIGNAL_UPDATE_ARLO)
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import ATTR_BATTERY_LEVEL
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)

ARLO_MODE_ARMED = 'armed'
ARLO_MODE_DISARMED = 'disarmed'

ATTR_BRIGHTNESS = 'brightness'
ATTR_FLIPPED = 'flipped'
ATTR_MIRRORED = 'mirrored'
ATTR_MOTION = 'motion_detection_sensitivity'
ATTR_POWERSAVE = 'power_save_mode'
ATTR_SIGNAL_STRENGTH = 'signal_strength'
ATTR_UNSEEN_VIDEOS = 'unseen_videos'
ATTR_LAST_REFRESH = 'last_refresh'

CONF_FFMPEG_ARGUMENTS = 'ffmpeg_arguments'

DEPENDENCIES = ['arlo', 'ffmpeg']

POWERSAVE_MODE_MAPPING = {
    1: 'best_battery_life',
    2: 'optimized',
    3: 'best_video'
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_FFMPEG_ARGUMENTS): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up an Arlo IP Camera."""
    arlo = hass.data[DATA_ARLO]

    cameras = []
    for camera in arlo.cameras:
        cameras.append(ArloCam(hass, camera, config))

    add_entities(cameras)


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
        self._last_refresh = None
        self.attrs = {}

    def camera_image(self):
        """Return a still image response from the camera."""
        return self._camera.last_image_from_cache

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_ARLO, self._update_callback)

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state()

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        from haffmpeg import CameraMjpeg
        video = self._camera.last_video
        if not video:
            error_msg = \
                'Video not found for {0}. Is it older than {1} days?'.format(
                    self.name, self._camera.min_days_vdo_cache)
            _LOGGER.error(error_msg)
            return

        stream = CameraMjpeg(self._ffmpeg.binary, loop=self.hass.loop)
        await stream.open_camera(
            video.video_url, extra_cmd=self._ffmpeg_arguments)

        try:
            return await async_aiohttp_proxy_stream(
                self.hass, request, stream,
                'multipart/x-mixed-replace;boundary=ffserver')
        finally:
            await stream.close()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            name: value for name, value in (
                (ATTR_BATTERY_LEVEL, self._camera.battery_level),
                (ATTR_BRIGHTNESS, self._camera.brightness),
                (ATTR_FLIPPED, self._camera.flip_state),
                (ATTR_MIRRORED, self._camera.mirror_state),
                (ATTR_MOTION, self._camera.motion_detection_sensitivity),
                (ATTR_POWERSAVE, POWERSAVE_MODE_MAPPING.get(
                    self._camera.powersave_mode)),
                (ATTR_SIGNAL_STRENGTH, self._camera.signal_strength),
                (ATTR_UNSEEN_VIDEOS, self._camera.unseen_videos),
            ) if value is not None
        }

    @property
    def model(self):
        """Return the camera model."""
        return self._camera.model_id

    @property
    def brand(self):
        """Return the camera brand."""
        return DEFAULT_BRAND

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return self._motion_status

    def set_base_station_mode(self, mode):
        """Set the mode in the base station."""
        # Get the list of base stations identified by library
        base_stations = self.hass.data[DATA_ARLO].base_stations

        # Some Arlo cameras does not have base station
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
