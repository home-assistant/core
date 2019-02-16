"""
Local optical character recognition processing using GOCR.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/image_processing.gocr/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.core import split_entity_id
from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA, ImageProcessingEntity, CONF_SOURCE, CONF_ENTITY_ID,
    CONF_NAME)

import shlex

_LOGGER = logging.getLogger(__name__)

CONF_UNRECOGNIZED = 'unrecognized'
CONF_CHARS = 'chars'
CONF_EXTRA_ARGUMENTS = 'extra_arguments'
CONF_HEIGHT = 'height'
CONF_ROTATE = 'rotate'
CONF_GOCR_BIN = 'gocr_bin'
CONF_THRESHOLD = 'threshold'
CONF_WIDTH = 'width'
CONF_X_POSITION = 'x_position'
CONF_Y_POSITION = 'y_position'
CONF_NEGATE = 'negate'

DEFAULT_BINARY = 'gocr'

_KEY_GEOMETRY = 'geometry'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_EXTRA_ARGUMENTS, default=''): cv.string,
    vol.Optional(CONF_UNRECOGNIZED): cv.string,
    vol.Optional(CONF_CHARS): cv.string,
    vol.Inclusive(CONF_HEIGHT, _KEY_GEOMETRY): cv.positive_int,
    vol.Inclusive(CONF_X_POSITION, _KEY_GEOMETRY): cv.positive_int,
    vol.Inclusive(CONF_WIDTH, _KEY_GEOMETRY): cv.positive_int,
    vol.Inclusive(CONF_Y_POSITION, _KEY_GEOMETRY): cv.positive_int,
    vol.Optional(CONF_GOCR_BIN, default=DEFAULT_BINARY): cv.string,
    vol.Optional(CONF_THRESHOLD): cv.positive_int,
    vol.Optional(CONF_ROTATE): cv.positive_int,

    vol.Optional(CONF_NEGATE, default=False): cv.boolean,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the GOCR platform."""
    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(ImageProcessingGocr(
            hass, camera[CONF_ENTITY_ID], config, camera.get(CONF_NAME)
        ))

    async_add_entities(entities)


class ImageProcessingGocr(ImageProcessingEntity):
    """Representation of GOCR image processing entity."""

    def __init__(self, hass, camera_entity, config, name):
        """Initialize text processing."""
        self._camera_entity = camera_entity
        if name is not None:
            self._name = name
        else:
            self._name = ("GOCR {0}".format(
                split_entity_id(camera_entity)[1])
                if config[CONF_NAME] == '' else
                config[CONF_NAME])
        self._state = None
        if config[CONF_X_POSITION] is not None:
            self.crop = (config[CONF_X_POSITION], config[CONF_Y_POSITION],
                         config[CONF_X_POSITION] + config[CONF_WIDTH],
                         config[CONF_Y_POSITION] + config[CONF_HEIGHT])
        else:
            self.crop = None
        self.rotate = config[CONF_ROTATE]
        self.negate = config[CONF_NEGATE]
        if config.get(CONF_CHARS) is not None:
            digits = ['-C', config.get(CONF_CHARS)]
        else:
            digits = []
        if config.get(CONF_UNRECOGNIZED) is not None:
            unrecognized = ['-u', config.get(CONF_UNRECOGNIZED)]
        else:
            unrecognized = []
        if config[CONF_THRESHOLD] is not None:
            threshold = ['-l', str(config[CONF_THRESHOLD])]
        else:
            threshold = []
        if config[CONF_EXTRA_ARGUMENTS] is not None:
            extra_arguments = shlex.split(config[CONF_EXTRA_ARGUMENTS])
        else:
            extra_arguments = []

        self._command = ([config[CONF_GOCR_BIN],
                         '-e', '/dev/null', '-f', 'UTF8'] +
                         digits + unrecognized + threshold +
                         extra_arguments)
        _LOGGER.info("Command : %s -i <tmpfile>",
                     shlex.quote(' '.join(self._command)))

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
        import PIL.ImageOps
        from subprocess import run, PIPE
        import io
        from tempfile import NamedTemporaryFile

        _LOGGER.debug("Start processing")

        stream = io.BytesIO(image)
        img = Image.open(stream)
        if self.crop is not None:
            img = img.crop(self.crop)
        if self.negate:
            img = PIL.ImageOps.invert(img)
        if self.rotate is not None:
            img = img.rotate(self.rotate, expand=1)
        tmp = NamedTemporaryFile(suffix='.ppm')
        self._state = None
        try:
            img.save(tmp.name)
            ocr = run(self._command + ['-i', tmp.name],
                      stdout=PIPE, encoding='utf-8')
            self._state = ocr.stdout[:255]
            _LOGGER.info("Processed: " + self._state)
        finally:
            tmp.close()

        if self._state is None:
            _LOGGER.error("Couldn't process image !")
