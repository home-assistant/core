"""
Camera that loads a picture from a local file.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.local_file/
"""
import logging
import mimetypes
import os

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.components.camera import (
    Camera, CAMERA_SERVICE_SCHEMA, DOMAIN, PLATFORM_SCHEMA)
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_FILE_PATH = 'file_path'
DEFAULT_NAME = 'Local File'
SERVICE_UPDATE_FILE_PATH = 'local_file_update_file_path'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_FILE_PATH): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})

CAMERA_SERVICE_UPDATE_FILE_PATH = CAMERA_SERVICE_SCHEMA.extend({
    vol.Required(CONF_FILE_PATH): cv.string
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Camera that works with local files."""
    file_path = config[CONF_FILE_PATH]
    camera = LocalFile(config[CONF_NAME], file_path)

    def update_file_path_service(call):
        """Update the file path."""
        file_path = call.data.get(CONF_FILE_PATH)
        camera.update_file_path(file_path)
        return True

    hass.services.register(
        DOMAIN,
        SERVICE_UPDATE_FILE_PATH,
        update_file_path_service,
        schema=CAMERA_SERVICE_UPDATE_FILE_PATH)

    add_entities([camera])


class LocalFile(Camera):
    """Representation of a local file camera."""

    def __init__(self, name, file_path):
        """Initialize Local File Camera component."""
        super().__init__()

        self._name = name
        self.check_file_path_access(file_path)
        self._file_path = file_path
        # Set content type of local file
        content, _ = mimetypes.guess_type(file_path)
        if content is not None:
            self.content_type = content

    def camera_image(self):
        """Return image response."""
        try:
            with open(self._file_path, 'rb') as file:
                return file.read()
        except FileNotFoundError:
            _LOGGER.warning("Could not read camera %s image from file: %s",
                            self._name, self._file_path)

    def check_file_path_access(self, file_path):
        """Check that filepath given is readable."""
        if not os.access(file_path, os.R_OK):
            _LOGGER.warning("Could not read camera %s image from file: %s",
                            self._name, file_path)

    def update_file_path(self, file_path):
        """Update the file_path."""
        self.check_file_path_access(file_path)
        self._file_path = file_path
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the camera state attributes."""
        return {
            'file_path': self._file_path,
        }
