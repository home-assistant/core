"""
Support for Netgear Arlo IP cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.arlo/
"""
import asyncio
import logging
from datetime import datetime, timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.arlo import DEFAULT_BRAND, DATA_ARLO
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import ATTR_BATTERY_LEVEL, STATE_UNKNOWN
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=90)

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
    '1': 'best_battery_life',
    '2': 'optimized',
    '3': 'best_video'
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_FFMPEG_ARGUMENTS):
    cv.string,
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
        self._last_refresh = None
        self.attrs = {}

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
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_BATTERY_LEVEL: self.attrs.get(ATTR_BATTERY_LEVEL),
            ATTR_BRIGHTNESS: self.attrs.get(ATTR_BRIGHTNESS),
            ATTR_FLIPPED: self.attrs.get(ATTR_FLIPPED),
            ATTR_MIRRORED: self.attrs.get(ATTR_MIRRORED),
            ATTR_MOTION: self.attrs.get(ATTR_MOTION),
            ATTR_POWERSAVE: self.attrs.get(ATTR_POWERSAVE),
            ATTR_SIGNAL_STRENGTH: self.attrs.get(ATTR_SIGNAL_STRENGTH),
            ATTR_UNSEEN_VIDEOS: self.attrs.get(ATTR_UNSEEN_VIDEOS),
            ATTR_LAST_REFRESH: self.attrs.get(ATTR_LAST_REFRESH),
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
    def should_poll(self):
        """Camera should poll periodically."""
        return True

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

    @staticmethod
    def clean_attr(attr):
        """Return unknown if attribute is None (non-subscriptable)."""
        return str(attr) if attr is not None else STATE_UNKNOWN

    def update(self):
        """Add an attribute-update task to the executor pool."""
        # pylint: disable=W0212
        base_stations = self._camera._session.base_stations

        if not base_stations:
            return None

        # pylint: disable=W0212
        base_stations[0]._refresh_rate = SCAN_INTERVAL.total_seconds()

        base_stations[0].update()
        self._camera.update()

        battery_level = self.clean_attr(self._camera.get_battery_level)
        brightness = self.clean_attr(self._camera.get_brightness)
        flip_state = self.clean_attr(self._camera.get_flip_state)
        mirror_state = self.clean_attr(self._camera.get_mirror_state)
        motion_sensitivity = self.clean_attr(
            self._camera.get_motion_detection_sensitivity)
        powersave_mode = self.clean_attr(self._camera.get_powersave_mode)
        signal_strength = self.clean_attr(self._camera.get_signal_strength)
        unseen_videos = self.clean_attr(self._camera.unseen_videos)

        self.attrs[ATTR_BATTERY_LEVEL] = battery_level
        self.attrs[ATTR_BRIGHTNESS] = brightness
        self.attrs[ATTR_FLIPPED] = flip_state
        self.attrs[ATTR_MIRRORED] = mirror_state
        self.attrs[ATTR_MOTION] = motion_sensitivity
        self.attrs[ATTR_POWERSAVE] = POWERSAVE_MODE_MAPPING[
            powersave_mode] if powersave_mode != STATE_UNKNOWN \
            else STATE_UNKNOWN
        self.attrs[ATTR_SIGNAL_STRENGTH] = signal_strength
        self.attrs[ATTR_UNSEEN_VIDEOS] = unseen_videos

        # pylint: disable=W0212
        self.attrs[ATTR_LAST_REFRESH] = datetime.fromtimestamp(
            base_stations[0]._last_refresh).strftime(
                "%A, %B %d, %Y %I:%M:%S") if base_stations[0]._last_refresh \
            else STATE_UNKNOWN
