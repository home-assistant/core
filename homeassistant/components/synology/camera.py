"""Support for Synology Surveillance Station Cameras."""
import logging

from synology.surveillance_station import SurveillanceStation
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.const import CONF_WHITELIST
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_web,
    async_get_clientsession,
)
import homeassistant.helpers.config_validation as cv

from .const import DATA_SURVEILLANCE_CLIENT, DATA_VERIFY_SSL, DOMAIN_DATA

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_WHITELIST, default=[]): cv.ensure_list}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a Synology IP Camera."""
    if hass.data[DOMAIN_DATA]:
        surveillance = hass.data[DOMAIN_DATA][DATA_SURVEILLANCE_CLIENT]
        if surveillance:
            # add cameras
            devices = []
            verify_ssl = hass.data[DOMAIN_DATA][DATA_VERIFY_SSL]

            cameras = surveillance.get_all_cameras()
            for camera in cameras:
                if not config[CONF_WHITELIST] or camera.name in config[CONF_WHITELIST]:
                    _LOGGER.debug("Synology camera %s configured", camera.name)
                    device = SynologyCamera(surveillance, camera.camera_id, verify_ssl)
                    devices.append(device)

            if len(devices) != 0:
                async_add_entities(devices)
            else:
                _LOGGER.info("No cameras were found on Synology NAS")


class SynologyCamera(Camera):
    """An implementation of a Synology NAS based IP camera."""

    def __init__(self, surveillance: SurveillanceStation, camera_id, verify_ssl):
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

    @property
    def should_poll(self):
        """Update the recording state periodically."""
        return True

    def update(self):
        """Update the status of the camera."""
        self._surveillance.update()
        self._camera = self._surveillance.get_camera(self._camera.camera_id)
        self._motion_setting = self._surveillance.get_motion_setting(
            self._camera.camera_id
        )
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
