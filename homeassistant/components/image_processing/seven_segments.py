"""
Local optical character recognition processing of seven segments displays.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/image_processing.seven_segments/
"""
import asyncio
import logging
import io
import os

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.core import split_entity_id
from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA, ImageProcessingEntity, CONF_SOURCE, CONF_ENTITY_ID,
    CONF_NAME)

_LOGGER = logging.getLogger(__name__)

CONF_DIGITS = 'digits'
CONF_EXTRA_ARGUMENTS = 'extra_arguments'
CONF_HEIGHT = 'height'
CONF_ROTATE = 'rotate'
CONF_SSOCR_BIN = 'ssocr_bin'
CONF_THRESHOLD = 'threshold'
CONF_WIDTH = 'width'
CONF_X_POS = 'x_position'
CONF_Y_POS = 'y_position'

DEFAULT_BINARY = 'ssocr'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_EXTRA_ARGUMENTS, default=''): cv.string,
    vol.Optional(CONF_DIGITS): cv.positive_int,
    vol.Optional(CONF_HEIGHT, default=0): cv.positive_int,
    vol.Optional(CONF_SSOCR_BIN, default=DEFAULT_BINARY): cv.string,
    vol.Optional(CONF_THRESHOLD, default=0): cv.positive_int,
    vol.Optional(CONF_ROTATE, default=0): cv.positive_int,
    vol.Optional(CONF_WIDTH, default=0): cv.positive_int,
    vol.Optional(CONF_X_POS, default=0): cv.string,
    vol.Optional(CONF_Y_POS, default=0): cv.positive_int,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
    """Set up the Seven segments OCR platform."""
    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(ImageProcessingSsocr(
            hass, camera[CONF_ENTITY_ID], config, camera.get(CONF_NAME)
        ))

    async_add_entities(entities)


class ImageProcessingSsocr(ImageProcessingEntity):
    """Representation of the seven segments OCR image processing entity."""

    def __init__(self, hass, camera_entity, config, name):
        """Initialize seven segments processing."""
        self.hass = hass
        self._camera_entity = camera_entity
        if name:
            self._name = name
        else:
            self._name = "SevenSegment OCR {0}".format(
                split_entity_id(camera_entity)[1])
        self._state = None

        self.filepath = os.path.join(self.hass.config.config_dir, 'ocr.png')
        crop = ['crop', str(config[CONF_X_POS]), str(config[CONF_Y_POS]),
                str(config[CONF_WIDTH]), str(config[CONF_HEIGHT])]
        digits = ['-d', str(config.get(CONF_DIGITS, -1))]
        rotate = ['rotate', str(config[CONF_ROTATE])]
        threshold = ['-t', str(config[CONF_THRESHOLD])]
        extra_arguments = config[CONF_EXTRA_ARGUMENTS].split(' ')

        self._command = [config[CONF_SSOCR_BIN]] + crop + digits + threshold +\
            rotate + extra_arguments
        self._command.append(self.filepath)

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'ocr'

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera_entity

    @property
    def name(self):
        """Return the name of the image processor."""
        return self._name

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    def process_image(self, image):
        """Process the image."""
        from PIL import Image
        import subprocess

        stream = io.BytesIO(image)
        img = Image.open(stream)
        img.save(self.filepath, 'png')

        ocr = subprocess.Popen(
            self._command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = ocr.communicate()
        if out[0] != b'':
            self._state = out[0].strip().decode('utf-8')
        else:
            self._state = None
            _LOGGER.warning(
                "Unable to detect value: %s", out[1].strip().decode('utf-8'))
