"""Support for Synology Surveillance Station Cameras."""
import logging

import requests
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD,
    CONF_URL, CONF_WHITELIST, CONF_VERIFY_SSL, CONF_TIMEOUT)
from homeassistant.components.camera import (
    Camera, PLATFORM_SCHEMA)
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_web,
    async_get_clientsession)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Synology Camera'
DEFAULT_TIMEOUT = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Optional(CONF_WHITELIST, default=[]): cv.ensure_list,
    vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up a Synology IP Camera."""
    verify_ssl = config.get(CONF_VERIFY_SSL)
    timeout = config.get(CONF_TIMEOUT)

    try:
        from synology.surveillance_station import SurveillanceStation
        surveillance = SurveillanceStation(
            config.get(CONF_URL),
            config.get(CONF_USERNAME),
            config.get(CONF_PASSWORD),
            verify_ssl=verify_ssl,
            timeout=timeout
        )
    except (requests.exceptions.RequestException, ValueError):
        _LOGGER.exception("Error when initializing SurveillanceStation")
        return False

    cameras = surveillance.get_all_cameras()

    # add cameras
    devices = []
    for camera in cameras:
        if not config.get(CONF_WHITELIST):
            device = SynologyCamera(surveillance, camera.camera_id, verify_ssl)
            devices.append(device)

    async_add_entities(devices)


class SynologyCamera(Camera):
    """An implementation of a Synology NAS based IP camera."""

    def __init__(self, surveillance, camera_id, verify_ssl):
        """Initialize a Synology Surveillance Station camera."""
        super().__init__()
        self._surveillance = surveillance
        self._camera_id = camera_id
        self._verify_ssl = verify_ssl
        self._camera = self._surveillance.get_camera(camera_id)
        self._motion_setting = self._surveillance.get_motion_setting(camera_id)
        self.is_streaming = self._camera.is_enabled

    def camera_image(self):
        """Return bytes of camera image."""
        return self._surveillance.get_camera_image(self._camera_id)

    async def handle_async_mjpeg_stream(self, request):
        """Return a MJPEG stream image response directly from the camera."""
        streaming_url = self._camera.video_stream_url

        websession = async_get_clientsession(self.hass, self._verify_ssl)
        stream_coro = websession.get(streaming_url)

        return await async_aiohttp_proxy_web(self.hass, request, stream_coro)

    @property
    def name(self):
        """Return the name of this device."""
        return self._camera.name

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return self._camera.is_recording

    def should_poll(self):
        """Update the recording state periodically."""
        return True

    def update(self):
        """Update the status of the camera."""
        self._surveillance.update()
        self._camera = self._surveillance.get_camera(self._camera.camera_id)
        self._motion_setting = self._surveillance.get_motion_setting(
            self._camera.camera_id)
        self.is_streaming = self._camera.is_enabled

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return self._motion_setting.is_enabled

    def enable_motion_detection(self):
        """Enable motion detection in the camera."""
        self._surveillance.enable_motion_detection(self._camera_id)

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        self._surveillance.disable_motion_detection(self._camera_id)
