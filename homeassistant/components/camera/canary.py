"""
Support for Canary camera.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.canary/
"""
import logging

import requests

from homeassistant.components.camera import Camera
from homeassistant.components.canary import DATA_CANARY, DEFAULT_TIMEOUT

DEPENDENCIES = ['canary']

_LOGGER = logging.getLogger(__name__)

ATTR_MOTION_START_TIME = "motion_start_time"
ATTR_MOTION_END_TIME = "motion_end_time"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Canary sensors."""
    data = hass.data[DATA_CANARY]
    devices = []

    for location in data.locations:
        entries = data.get_motion_entries(location.location_id)
        if entries:
            devices.append(CanaryCamera(data, location.location_id,
                                        DEFAULT_TIMEOUT))

    add_devices(devices, True)


class CanaryCamera(Camera):
    """An implementation of a Canary security camera."""

    def __init__(self, data, location_id, timeout):
        """Initialize a Canary security camera."""
        super().__init__()
        self._data = data
        self._location_id = location_id
        self._timeout = timeout

        self._location = None
        self._motion_entry = None
        self._image_content = None

    def camera_image(self):
        """Update the status of the camera and return bytes of camera image."""
        self.update()
        return self._image_content

    @property
    def name(self):
        """Return the name of this device."""
        return self._location.name

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return self._location.is_recording

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        if self._motion_entry is None:
            return None

        return {
            ATTR_MOTION_START_TIME: self._motion_entry.start_time,
            ATTR_MOTION_END_TIME: self._motion_entry.end_time,
        }

    def update(self):
        """Update the status of the camera."""
        self._data.update()
        self._location = self._data.get_location(self._location_id)

        entries = self._data.get_motion_entries(self._location_id)
        if entries:
            current = entries[0]
            previous = self._motion_entry

            if previous is None or previous.entry_id != current.entry_id:
                self._motion_entry = current
                self._image_content = requests.get(
                    current.thumbnails[0].image_url,
                    timeout=self._timeout).content

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return not self._location.is_recording
