"""
Camera platform that has a Raspberry Pi camera.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.rpi_camera/
"""
import os
import subprocess
import logging
import shutil
from tempfile import NamedTemporaryFile

import voluptuous as vol

from homeassistant.components.camera import (Camera, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_NAME, CONF_FILE_PATH,
                                 EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_HORIZONTAL_FLIP = 'horizontal_flip'
CONF_IMAGE_HEIGHT = 'image_height'
CONF_IMAGE_QUALITY = 'image_quality'
CONF_IMAGE_ROTATION = 'image_rotation'
CONF_IMAGE_WIDTH = 'image_width'
CONF_TIMELAPSE = 'timelapse'
CONF_VERTICAL_FLIP = 'vertical_flip'

DEFAULT_HORIZONTAL_FLIP = 0
DEFAULT_IMAGE_HEIGHT = 480
DEFAULT_IMAGE_QUALITY = 7
DEFAULT_IMAGE_ROTATION = 0
DEFAULT_IMAGE_WIDTH = 640
DEFAULT_NAME = 'Raspberry Pi Camera'
DEFAULT_TIMELAPSE = 1000
DEFAULT_VERTICAL_FLIP = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_FILE_PATH): cv.isfile,
    vol.Optional(CONF_HORIZONTAL_FLIP, default=DEFAULT_HORIZONTAL_FLIP):
        vol.All(vol.Coerce(int), vol.Range(min=0, max=1)),
    vol.Optional(CONF_IMAGE_HEIGHT, default=DEFAULT_IMAGE_HEIGHT):
        vol.Coerce(int),
    vol.Optional(CONF_IMAGE_QUALITY, default=DEFAULT_IMAGE_QUALITY):
        vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    vol.Optional(CONF_IMAGE_ROTATION, default=DEFAULT_IMAGE_ROTATION):
        vol.All(vol.Coerce(int), vol.Range(min=0, max=359)),
    vol.Optional(CONF_IMAGE_WIDTH, default=DEFAULT_IMAGE_WIDTH):
        vol.Coerce(int),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TIMELAPSE, default=1000): vol.Coerce(int),
    vol.Optional(CONF_VERTICAL_FLIP, default=DEFAULT_VERTICAL_FLIP):
        vol.All(vol.Coerce(int), vol.Range(min=0, max=1)),
})


def kill_raspistill(*args):
    """Kill any previously running raspistill process.."""
    subprocess.Popen(['killall', 'raspistill'],
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.STDOUT)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Raspberry Camera."""
    if shutil.which("raspistill") is None:
        _LOGGER.error("'raspistill' was not found")
        return False

    setup_config = (
        {
            CONF_NAME: config.get(CONF_NAME),
            CONF_IMAGE_WIDTH: config.get(CONF_IMAGE_WIDTH),
            CONF_IMAGE_HEIGHT: config.get(CONF_IMAGE_HEIGHT),
            CONF_IMAGE_QUALITY: config.get(CONF_IMAGE_QUALITY),
            CONF_IMAGE_ROTATION: config.get(CONF_IMAGE_ROTATION),
            CONF_TIMELAPSE: config.get(CONF_TIMELAPSE),
            CONF_HORIZONTAL_FLIP: config.get(CONF_HORIZONTAL_FLIP),
            CONF_VERTICAL_FLIP: config.get(CONF_VERTICAL_FLIP),
            CONF_FILE_PATH: config.get(CONF_FILE_PATH)
        }
    )

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, kill_raspistill)

    file_path = setup_config[CONF_FILE_PATH]

    def delete_temp_file(*args):
        """Delete the temporary file to prevent saving multiple temp images.

        Only used when no path is defined
        """
        os.remove(file_path)

    # If no file path is defined, use a temporary file
    if file_path is None:
        temp_file = NamedTemporaryFile(suffix='.jpg', delete=False)
        temp_file.close()
        file_path = temp_file.name
        setup_config[CONF_FILE_PATH] = file_path
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, delete_temp_file)

    # Check whether the file path has been whitelisted
    elif not hass.config.is_allowed_path(file_path):
        _LOGGER.error("'%s' is not a whitelisted directory", file_path)
        return False

    add_entities([RaspberryCamera(setup_config)])


class RaspberryCamera(Camera):
    """Representation of a Raspberry Pi camera."""

    def __init__(self, device_info):
        """Initialize Raspberry Pi camera component."""
        super().__init__()

        self._name = device_info[CONF_NAME]
        self._config = device_info

        # Kill if there's raspistill instance
        kill_raspistill()

        cmd_args = [
            'raspistill', '--nopreview', '-o', device_info[CONF_FILE_PATH],
            '-t', '0', '-w', str(device_info[CONF_IMAGE_WIDTH]),
            '-h', str(device_info[CONF_IMAGE_HEIGHT]),
            '-tl', str(device_info[CONF_TIMELAPSE]),
            '-q', str(device_info[CONF_IMAGE_QUALITY]),
            '-rot', str(device_info[CONF_IMAGE_ROTATION])
        ]
        if device_info[CONF_HORIZONTAL_FLIP]:
            cmd_args.append("-hf")

        if device_info[CONF_VERTICAL_FLIP]:
            cmd_args.append("-vf")

        subprocess.Popen(cmd_args,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.STDOUT)

    def camera_image(self):
        """Return raspistill image response."""
        with open(self._config[CONF_FILE_PATH], 'rb') as file:
            return file.read()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
