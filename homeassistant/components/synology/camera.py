"""Support for Synology Surveillance Station Cameras."""
from functools import partial
import logging

import requests
from synology.surveillance_station import SurveillanceStation

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_web,
    async_get_clientsession,
)
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Synology cameras."""
    try:
        surveillance = await hass.async_add_executor_job(
            partial(
                SurveillanceStation,
                entry.data[CONF_URL],
                entry.data[CONF_USERNAME],
                entry.data[CONF_PASSWORD],
                verify_ssl=entry.data[CONF_VERIFY_SSL],
                timeout=entry.data[CONF_TIMEOUT],
            )
        )
    except requests.exceptions.RequestException as err:
        _LOGGER.warning("Error when initializing SurveillanceStation: %s", err)
        raise ConfigEntryNotReady

    cameras = surveillance.get_all_cameras()

    # add cameras
    devices = []
    for camera in cameras:
        device = SynologyCamera(
            surveillance, camera.camera_id, entry.data[CONF_VERIFY_SSL], entry.entry_id
        )
        devices.append(device)

    async_add_entities(devices)


class SynologyCamera(Camera):
    """An implementation of a Synology NAS based IP camera."""

    def __init__(self, surveillance, camera_id, verify_ssl, entry_id):
        """Initialize a Synology Surveillance Station camera."""
        super().__init__()
        self._surveillance = surveillance
        self._camera_id = camera_id
        self._verify_ssl = verify_ssl
        self._entry_id = entry_id
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
    def unique_id(self):
        """Return the unique id of the device."""
        return f"{self._entry_id}-{self._camera_id}"

    @property
    def device_info(self):
        """Return the device info if the device."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "manufacturer": "Synology",
            "name": self.name,
            "via_device": (DOMAIN, self._entry_id),
        }

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
