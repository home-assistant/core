"""Camera that loads a picture from a local file."""

import logging
import os

from homeassistant.components.camera import Camera

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Camera."""
    # check for missing required configuration variable
    if config.get("file_path") is None:
        _LOGGER.error("Missing required variable: file_path")
        return False

    setup_config = (
        {
            "name": config.get("name", "Local File"),
            "file_path": config.get("file_path")
        }
    )

    # check filepath given is readable
    if not os.access(setup_config["file_path"], os.R_OK):
        _LOGGER.error("file path is not readable")
        return False

    add_devices([
        LocalFile(setup_config)
    ])


class LocalFile(Camera):
    """Local camera."""

    def __init__(self, device_info):
        """Initialize Local File Camera component."""
        super().__init__()

        self._name = device_info["name"]
        self._config = device_info

    def camera_image(self):
        """Return image response."""
        with open(self._config["file_path"], 'rb') as file:
            return file.read()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
