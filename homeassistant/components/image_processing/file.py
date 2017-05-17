"""
Storing images to file from a given source.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/image_processing.file/
"""
import io
import logging
import os

import voluptuous as vol

import homeassistant.util.dt as dt_util
import homeassistant.helpers.config_validation as cv
from homeassistant.core import split_entity_id
from homeassistant.components.image_processing import (
    ImageProcessingEntity, PLATFORM_SCHEMA)
from homeassistant.components.image_processing import (
    CONF_SOURCE, CONF_ENTITY_ID, CONF_NAME)

REQUIREMENTS = ['Pillow==4.1.1']

_LOGGER = logging.getLogger(__name__)

CONF_FILE_PATH = 'file_path'
CONF_IMAGE_TYPE = 'image_type'
CONF_TIMESTAMP = 'timestamp'

DEFAULT_IMAGE_TYPE = 'png'
DEFAULT_TIMESTAMP = False

SUPPORTED_IMAGE_TYPES = ['png', 'jpg']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_FILE_PATH): cv.string,
    vol.Optional(CONF_IMAGE_TYPE, default=DEFAULT_IMAGE_TYPE):
        vol.In(SUPPORTED_IMAGE_TYPES),
    vol.Optional(CONF_TIMESTAMP, default=DEFAULT_TIMESTAMP): cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the File storage platform."""
    file_path = config.get(CONF_FILE_PATH)
    image_type = config.get(CONF_IMAGE_TYPE)
    timestamp = config.get(CONF_TIMESTAMP)

    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(FileStorage(
            camera[CONF_ENTITY_ID], file_path, image_type, timestamp,
            camera.get(CONF_NAME)))

    add_devices(entities)


class FileStorage(ImageProcessingEntity):
    """Representation of a File Storage entity."""

    def __init__(
            self, camera_entity, file_path, image_type, timestamp, name=None):
        """Initialize the File Storage entity."""
        self._camera = camera_entity
        self._file_path = file_path
        self._image_type = image_type
        self._timestamp = timestamp
        self._files = 0
        if name:
            self._name = name
        else:
            self._name = "File storage Camera {0}".format(
                split_entity_id(camera_entity)[1])

        self._file_name = self._name.lower().replace(' ', '-')

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def state(self):
        """Return the state of the entity."""
        return self._files

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    def process_image(self, image):
        """Process image."""
        from PIL import Image, ImageFont, ImageDraw

        current_timestamp = dt_util.utcnow().isoformat()
        file_name = '{}-{}.{}'.format(
            self._file_name, current_timestamp, self._image_type)

        self._files = self._files + 1
        stream = io.BytesIO(image)
        img = Image.open(stream)

        if self._timestamp:
            font = ImageFont.load_default()
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), current_timestamp, font=font)

        filepath = os.path.join(self._file_path, file_name)
        try:
            img.save(filepath, self._image_type)
        except FileNotFoundError:
            _LOGGER.warning("Path does not exist: %s", self._file_path)
