"""
Support for Canary Security Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.canary/
"""
import logging

import requests

from homeassistant.components.camera import Camera
from homeassistant.components.canary import DATA_CANARY

DEPENDENCIES = ['canary']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Canary sensors."""
    data = hass.data[DATA_CANARY]
    devices = []

    for location in data.locations:
        entries = data.get_motion_entries(location.location_id)
        if len(entries) > 0:
            devices.append(CanaryCamera(data, location))

    add_devices(devices, True)


class CanaryCamera(Camera):
    """An implementation of a Canary security camera."""

    def __init__(self, data, location):
        """Initialize a Canary security camera."""
        super().__init__()
        self._data = data
        self._location = location

        self._thumbnail = None
        self._image_url = None
        self._image_content = None

        self.update()

    def camera_image(self):
        """Return bytes of camera image."""
        if self._thumbnail is None:
            return None

        if self._image_url != self._thumbnail.image_url:
            self._image_url = self._thumbnail.image_url
            self._image_content = requests.get(self._image_url).content

        return self._image_content

    @property
    def name(self):
        """Return the name of this device."""
        return self._location.name

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return not self._location.is_private

    def should_poll(self):
        """Update the recording state periodically."""
        return True

    def update(self):
        """Update the status of the camera."""
        self._data.update()

        entries = self._data.get_motion_entries(self._location.location_id)

        if len(entries) > 0:
            self._thumbnail = entries[0].thumbnails[0]

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return not self._location.is_private
