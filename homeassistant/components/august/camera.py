"""Support for August camera."""
from datetime import timedelta

import requests

from homeassistant.components.camera import Camera

from . import DATA_AUGUST, DEFAULT_TIMEOUT

SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up August cameras."""
    data = hass.data[DATA_AUGUST]
    devices = []

    for doorbell in data.doorbells:
        devices.append(AugustCamera(data, doorbell, DEFAULT_TIMEOUT))

    async_add_entities(devices, True)


class AugustCamera(Camera):
    """An implementation of a August security camera."""

    def __init__(self, data, doorbell, timeout):
        """Initialize a August security camera."""
        super().__init__()
        self._data = data
        self._doorbell = doorbell
        self._timeout = timeout
        self._image_url = None
        self._image_content = None

    @property
    def name(self):
        """Return the name of this device."""
        return self._doorbell.device_name

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return self._doorbell.has_subscription

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return True

    @property
    def brand(self):
        """Return the camera brand."""
        return "August"

    @property
    def model(self):
        """Return the camera model."""
        return "Doorbell"

    async def async_camera_image(self):
        """Return bytes of camera image."""
        latest = await self._data.async_get_doorbell_detail(self._doorbell.device_id)

        if self._image_url is not latest.image_url:
            self._image_url = latest.image_url
            self._image_content = await self.hass.async_add_executor_job(
                self._camera_image
            )

        return self._image_content

    def _camera_image(self):
        """Return bytes of camera image via http get."""
        # Move this to py-august: see issue#32048
        return requests.get(self._image_url, timeout=self._timeout).content

    @property
    def unique_id(self) -> str:
        """Get the unique id of the camera."""
        return f"{self._doorbell.device_id:s}_camera"
