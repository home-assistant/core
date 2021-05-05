"""Camera that loads a picture from a local file."""
import logging
import mimetypes
import os

import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.const import ATTR_ENTITY_ID, CONF_FILE_PATH, CONF_NAME
from homeassistant.helpers import config_validation as cv

from .const import DATA_LOCAL_FILE, DEFAULT_NAME, DOMAIN, SERVICE_UPDATE_FILE_PATH

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_FILE_PATH): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

CAMERA_SERVICE_UPDATE_FILE_PATH = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
        vol.Required(CONF_FILE_PATH): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Camera that works with local files."""
    if DATA_LOCAL_FILE not in hass.data:
        hass.data[DATA_LOCAL_FILE] = []

    file_path = config[CONF_FILE_PATH]
    camera = LocalFile(config[CONF_NAME], file_path)
    hass.data[DATA_LOCAL_FILE].append(camera)

    def update_file_path_service(call):
        """Update the file path."""
        file_path = call.data.get(CONF_FILE_PATH)
        entity_ids = call.data.get(ATTR_ENTITY_ID)
        cameras = hass.data[DATA_LOCAL_FILE]

        for camera in cameras:
            if camera.entity_id in entity_ids:
                camera.update_file_path(file_path)
        return True

    hass.services.register(
        DOMAIN,
        SERVICE_UPDATE_FILE_PATH,
        update_file_path_service,
        schema=CAMERA_SERVICE_UPDATE_FILE_PATH,
    )

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
            with open(self._file_path, "rb") as file:
                return file.read()
        except FileNotFoundError:
            _LOGGER.warning(
                "Could not read camera %s image from file: %s",
                self._name,
                self._file_path,
            )

    def check_file_path_access(self, file_path):
        """Check that filepath given is readable."""
        if not os.access(file_path, os.R_OK):
            _LOGGER.warning(
                "Could not read camera %s image from file: %s", self._name, file_path
            )

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
    def extra_state_attributes(self):
        """Return the camera state attributes."""
        return {"file_path": self._file_path}
