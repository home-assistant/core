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

ATTR_MOTION_START_TIME = "motion_start_time"
ATTR_MOTION_END_TIME = "motion_end_time"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Canary sensors."""
    data = hass.data[DATA_CANARY]
    devices = []

    for location in data.locations:
        entries = data.get_motion_entries(location.location_id)
        if entries:
            devices.append(CanaryCamera(data, location.location_id))

    add_devices(devices, True)


class CanaryCamera(Camera):
    """An implementation of a Canary security camera."""

    def __init__(self, data, location_id):
        """Initialize a Canary security camera."""
        super().__init__()
        self._data = data
        self._location_id = location_id

        self._location = None
        self._last_entry = None
        self._image_content = None
        self._force_update = False

        self.update()

    def camera_image(self):
        """Return bytes of camera image."""
        return self._image_content

    @property
    def name(self):
        """Return the name of this device."""
        return self._location.name

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return not self._location.is_private

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        if self._last_entry is None:
            return None

        return {
            ATTR_MOTION_START_TIME: self._last_entry.start_time,
            ATTR_MOTION_END_TIME: self._last_entry.end_time,
        }

    @property
    def force_update(self) -> bool:
        """Return True if state updates should be forced."""
        if self._force_update:
            self._force_update = False
            return True

        return False

    def should_poll(self):
        """Update the recording state periodically."""
        return True

    def update(self):
        """Update the status of the camera."""
        self._data.update()
        self._location = self._data.get_location(self._location_id)

        entries = self._data.get_motion_entries(self._location_id)
        if entries:
            current_entry = entries[0]

            if self._last_entry is None \
                    or self._last_entry.entry_id != current_entry.entry_id:
                thumbnail = current_entry.thumbnails[0]
                self._image_content = requests.get(thumbnail.image_url).content
                self._last_entry = current_entry
                self._force_update = True

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return not self._location.is_private
