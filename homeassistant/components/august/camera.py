"""Support for August camera."""
from datetime import timedelta

import requests

from homeassistant.components.camera import Camera

from . import DATA_AUGUST, DEFAULT_TIMEOUT

SCAN_INTERVAL = timedelta(seconds=5)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up August cameras."""
    data = hass.data[DATA_AUGUST]
    devices = []

    for doorbell in data.doorbells:
        devices.append(AugustCamera(data, doorbell, DEFAULT_TIMEOUT))

    add_entities(devices, True)


class AugustCamera(Camera):
    """An implementation of a Canary security camera."""

    def __init__(self, data, doorbell, timeout):
        """Initialize a Canary security camera."""
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
        return 'August'

    @property
    def model(self):
        """Return the camera model."""
        return 'Doorbell'

    def camera_image(self):
        """Return bytes of camera image."""
        latest = self._data.get_doorbell_detail(self._doorbell.device_id)

        if self._image_url is not latest.image_url:
            self._image_url = latest.image_url
            self._image_content = requests.get(self._image_url,
                                               timeout=self._timeout).content

        return self._image_content

    @property
    def unique_id(self) -> str:
        """Get the unique id of the camera."""
        return '{:s}_camera'.format(self._doorbell.device_id)
