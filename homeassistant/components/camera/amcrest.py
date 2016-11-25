"""
This component provides basic support for Amcrest IP cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.amcrest/
"""
import logging
import voluptuous as vol

from homeassistant.components.camera import (Camera, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_PORT)
from homeassistant.helpers import config_validation as cv

REQUIREMENTS = ['amcrest==1.0.0']

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 80
DEFAULT_NAME = 'Amcrest Camera'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup an Amcrest IP Camera."""
    add_devices([AmcrestCam(config)])
    return True


class AmcrestCam(Camera):
    """An implementation of an Amcrest IP camera."""

    def __init__(self, device_info):
        """Initialize an Amcrest camera."""
        super(AmcrestCam, self).__init__()

        self._name = device_info.get(CONF_NAME)

        from amcrest import AmcrestCamera
        self._data = AmcrestCamera(device_info.get(CONF_HOST),
                                   device_info.get(CONF_PORT),
                                   device_info.get(CONF_USERNAME),
                                   device_info.get(CONF_PASSWORD))

    def camera_image(self):
        """Return a still image reponse from the camera."""
        # Send the request to snap a picture and return raw jpg data
        response = self._data.camera.snapshot()
        return response.data

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
