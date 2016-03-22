"""Camera platform that has a Raspberry Pi camera."""

import os
import subprocess
import logging
import shutil

from homeassistant.components.camera import Camera

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Raspberry Camera."""
    if shutil.which("raspistill") is None:
        _LOGGER.error("Error: raspistill not found")
        return None

    horizontal_flip_arg = ""
    horizontal_flip = int(config.get("horizontal_flip", "0"))
    if horizontal_flip:
        horizontal_flip_arg = " -hf "

    vertical_flip_arg = ""
    vertical_flip = int(config.get("vertical_flip", "0"))
    if vertical_flip:
        vertical_flip_arg = " -vf"

    setup_config = (
        {
            "name": config.get("name", "Raspberry Pi Camera"),
            "image_width": int(config.get("image_width", "640")),
            "image_height": int(config.get("image_height", "480")),
            "image_quality": int(config.get("image_quality", "7")),
            "image_rotation": int(config.get("image_rotation", "0")),
            "timelapse": int(config.get("timelapse", "1000")),
            "horizontal_flip_arg": horizontal_flip_arg,
            "vertical_flip_arg": vertical_flip_arg
        }
    )

    add_devices([
        RaspberryCamera(setup_config)
    ])


class RaspberryCamera(Camera):
    """Raspberry Pi camera."""

    def __init__(self, device_info):
        """Initialize Raspberry Pi camera component."""
        super().__init__()

        self._name = device_info["name"]

        image_path = os.path.join(os.path.dirname(__file__),
                                  'image.jpg')

        # kill if there's raspistill instance
        cmd = 'killall raspistill'
        subprocess.call(cmd, shell=True)
        # start new instance of raspistill
        cmd = ('raspistill --nopreview -o ' + str(image_path) +
               ' -t 0 ' + '-w ' + str(device_info["image_width"]) +
               ' -h ' + str(device_info["image_height"]) +
               ' -tl ' + str(device_info["timelapse"]) +
               ' -q ' + str(device_info["image_quality"]) +
               str(device_info["horizontal_flip_arg"]) +
               str(device_info["vertical_flip_arg"]) +
               ' -rot ' + str(device_info["image_rotation"]) +
               ' &')

        subprocess.call(cmd, shell=True)

    def camera_image(self):
        """Return raspstill image response."""
        image_path = os.path.join(os.path.dirname(__file__),
                                  'image.jpg')

        with open(image_path, 'rb') as file:
            return file.read()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
