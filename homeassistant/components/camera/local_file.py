"""
Camera that loads a picture from a local file.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.local_file/
"""
import logging
import os

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_FILE_PATH = 'file_path'

DEFAULT_NAME = 'Local File'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_FILE_PATH): cv.isfile,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Camera."""
    file_path = config[CONF_FILE_PATH]

    # check filepath given is readable
    if not os.access(file_path, os.R_OK):
        _LOGGER.error("file path is not readable")
        return False

    add_devices([LocalFile(config[CONF_NAME], file_path)])


class LocalFile(Camera):
    """Local camera."""

    def __init__(self, name, file_path):
        """Initialize Local File Camera component."""
        super().__init__()

        self._name = name
        self._file_path = file_path

    def camera_image(self):
        """Return image response."""
        with open(self._file_path, 'rb') as file:
            return file.read()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
