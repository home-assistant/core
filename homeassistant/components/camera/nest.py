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

SIMULATOR_SNAPSHOT_URL = 'https://developer.nest.com/simulator/api/v1/nest/devices/camera/snapshot'

NEST_BRAND = "Nest"

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup a Nest Cam."""
    if discovery_info is None:
        return
    camera_devices = hass.data[nest.DATA_NEST].camera_devices()
    cameras = [NestCamera(structure, device)
               for structure, device in camera_devices]
    add_devices(cameras)


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
        self._last_image_at = None

    # FIXME ends up with double name, ie Hallway(Hallway (E5C0))... maybe that's just the simulator?
    # FIXME duplication with climate/nest
    @property
    def name(self):
        """Return the name of the nest, if any."""
        return self._name
        #if self._location is None or self._location == self._name:
        #    return self._name
        #else:
        #    if self._name == '':
        #        return self._location.capitalize()
        #    else:
        #        return self._location.capitalize() + '(' + self._name + ')'

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return self._is_streaming

    @property
    def brand(self):
        """Camera Brand."""
        return NEST_BRAND

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

    def _ready_to_update_camera_image(self, now):
        return self._last_image_at is None or \
                utcnow() > self._last_image_at + self._time_between_snapshots

    def camera_image(self):
        """Return a still image response from the camera."""
        now = utcnow()
        if self._ready_to_update_camera_image(now):
            url = self.device.snapshot_url
            # sadly, can't test against a simulator
            if url == SIMULATOR_SNAPSHOT_URL:
                url = 'https://media.giphy.com/media/WCwFvyeb6WJna/giphy.gif'

            try:
                response = requests.get(url)
            except requests.exceptions.RequestException as error:
                _LOGGER.error('Error getting camera image: %s', error)
                return None

            self._last_image_at = now
            self._last_image = response.content

        return self._last_image
