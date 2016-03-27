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
        return False

    setup_config = (
        {
            "name": config.get("name", "Raspberry Pi Camera"),
            "image_width": int(config.get("image_width", "640")),
            "image_height": int(config.get("image_height", "480")),
            "image_quality": int(config.get("image_quality", "7")),
            "image_rotation": int(config.get("image_rotation", "0")),
            "timelapse": int(config.get("timelapse", "2000")),
            "horizontal_flip": int(config.get("horizontal_flip", "0")),
            "vertical_flip": int(config.get("vertical_flip", "0")),
            "file_path": config.get("file_path",
                                    os.path.join(os.path.dirname(__file__),
                                                 'image.jpg'))
        }
    )

    # check filepath given is writable
    if not os.access(setup_config["file_path"], os.W_OK):
        _LOGGER.error("Error: file path is not writable")
        return False

    add_devices([
        RaspberryCamera(setup_config)
    ])


class RaspberryCamera(Camera):
    """Raspberry Pi camera."""

    def __init__(self, device_info):
        """Initialize Raspberry Pi camera component."""
        super().__init__()

        self._name = device_info["name"]
        self._config = device_info

        # kill if there's raspistill instance
        subprocess.Popen(['killall', 'raspistill'],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.STDOUT)

        cmd_args = [
            'raspistill', '--nopreview', '-o', str(device_info["file_path"]),
            '-t', '0', '-w', str(device_info["image_width"]),
            '-h', str(device_info["image_height"]),
            '-tl', str(device_info["timelapse"]),
            '-q', str(device_info["image_quality"]),
            '-rot', str(device_info["image_rotation"])
        ]
        if device_info["horizontal_flip"]:
            cmd_args.append("-hf")

        if device_info["vertical_flip"]:
            cmd_args.append("-vf")

        subprocess.Popen(cmd_args,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.STDOUT)

    def camera_image(self):
        """Return raspstill image response."""
        with open(self._config["file_path"], 'rb') as file:
            return file.read()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
