"""
Support for Nest Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.nest/
"""

import logging
from datetime import timedelta
import requests
from IPython import embed
# import voluptuous as vol
from homeassistant.components.camera import (PLATFORM_SCHEMA, Camera)
import homeassistant.components.nest as nest
from homeassistant.util import Throttle


DEPENDENCIES = ['nest']
_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({})
# 2/minute for 
# TODO be NestAware subscription aware, (10/min subscribed, 2/min otherwise)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup a generic IP Camera."""
    add_devices([NestCamera(structure, device)
                 for structure, device in nest.camera_devices()])


class NestCamera(Camera):
    """Representation of a Nest Camera."""

    def __init__(self, structure, device):
        """Initialize a Nest Camera."""
        super().__init__()
        self.structure = structure
        self.device = device
        print(device.snapshot_url)
        embed()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def camera_image(self):
        """Return a still image response from the camera."""
        url = self.device.snapshot_url
        try:
            response = requests.get(url)
            print(response.content)
        except requests.exceptions.RequestException as error:
            _LOGGER.error('Error getting camera image: %s', error)
            return None
        
            _LOGGER.error('Error getting camera image: %s', error)
            return None

        return response.content
