"""
Support for Nest Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.nest/
"""

import logging
from datetime import timedelta
import requests
from homeassistant.components.camera import (PLATFORM_SCHEMA, Camera)
import homeassistant.components.nest as nest
from homeassistant.util.dt import utcnow


DEPENDENCIES = ['nest']
_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({})

NEST_BRAND = "Nest"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup a Nest Cam."""
    if discovery_info is None:
        return

    camera_devices = hass.data[nest.DATA_NEST].camera_devices()
    cameras = [NestCamera(structure, device)
               for structure, device in camera_devices]
    add_devices(cameras, True)


class NestCamera(Camera):
    """Representation of a Nest Camera."""

    def __init__(self, structure, device):
        """Initialize a Nest Camera."""
        super(NestCamera, self).__init__()
        self.structure = structure
        self.device = device

        # data attributes
        self._location = None
        self._name = None
        self._is_online = None
        self._is_streaming = None
        self._is_video_history_enabled = False
        # default to non-NestAware subscribed, but will be fixed during update
        self._time_between_snapshots = timedelta(seconds=30)
        self._last_image = None
        self._next_snapshot_at = None

    @property
    def name(self):
        """Return the name of the nest, if any."""
        return self._name

    @property
    def should_poll(self):
        """Nest camera should poll periodically."""
        return True

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return self._is_streaming

    @property
    def brand(self):
        """Camera Brand."""
        return NEST_BRAND

    # this doesn't seem to be getting called regularly, for some reason
    def update(self):
        """Cache value from Python-nest."""
        self._location = self.device.where
        self._name = self.device.name
        self._is_online = self.device.is_online
        self._is_streaming = self.device.is_streaming
        self._is_video_history_enabled = self.device.is_video_history_enabled

        if self._is_video_history_enabled:
            # NestAware allowed 10/min
            self._time_between_snapshots = timedelta(seconds=6)
        else:
            # otherwise, 2/min
            self._time_between_snapshots = timedelta(seconds=30)

    def _ready_for_snapshot(self, now):
        return (self._next_snapshot_at is None or
                now > self._next_snapshot_at)

    def camera_image(self):
        """Return a still image response from the camera."""
        now = utcnow()
        if self._ready_for_snapshot(now):
            url = self.device.snapshot_url

            try:
                response = requests.get(url)
            except requests.exceptions.RequestException as error:
                _LOGGER.error('Error getting camera image: %s', error)
                return None

            self._next_snapshot_at = now + self._time_between_snapshots
            self._last_image = response.content

        return self._last_image
