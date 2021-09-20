"""Camera platform that has a Raspberry Pi camera."""
import logging
import os
import shutil
import subprocess
from tempfile import NamedTemporaryFile

from homeassistant.components.camera import Camera
from homeassistant.const import CONF_FILE_PATH, CONF_NAME, EVENT_HOMEASSISTANT_STOP

from .const import (
    CONF_HORIZONTAL_FLIP,
    CONF_IMAGE_HEIGHT,
    CONF_IMAGE_QUALITY,
    CONF_IMAGE_ROTATION,
    CONF_IMAGE_WIDTH,
    CONF_OVERLAY_METADATA,
    CONF_OVERLAY_TIMESTAMP,
    CONF_TIMELAPSE,
    CONF_VERTICAL_FLIP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def kill_raspistill(*args):
    """Kill any previously running raspistill process.."""
    subprocess.Popen(
        ["killall", "raspistill"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
    )


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Raspberry Camera."""
    # We only want this platform to be set up via discovery.
    # prevent initializing by erroneous platform config section in yaml conf
    if discovery_info is None:
        return

    if shutil.which("raspistill") is None:
        _LOGGER.error("'raspistill' was not found")
        return

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, kill_raspistill)

    setup_config = hass.data[DOMAIN]
    file_path = setup_config[CONF_FILE_PATH]

    def delete_temp_file(*args):
        """Delete the temporary file to prevent saving multiple temp images.

        Only used when no path is defined
        """
        os.remove(file_path)

    # If no file path is defined, use a temporary file
    if file_path is None:
        with NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
            file_path = temp_file.name
        setup_config[CONF_FILE_PATH] = file_path
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, delete_temp_file)

    # Check whether the file path has been whitelisted
    elif not hass.config.is_allowed_path(file_path):
        _LOGGER.error("'%s' is not a whitelisted directory", file_path)
        return

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
            "raspistill",
            "--nopreview",
            "-o",
            device_info[CONF_FILE_PATH],
            "-t",
            "0",
            "-w",
            str(device_info[CONF_IMAGE_WIDTH]),
            "-h",
            str(device_info[CONF_IMAGE_HEIGHT]),
            "-tl",
            str(device_info[CONF_TIMELAPSE]),
            "-q",
            str(device_info[CONF_IMAGE_QUALITY]),
            "-rot",
            str(device_info[CONF_IMAGE_ROTATION]),
        ]
        if device_info[CONF_HORIZONTAL_FLIP]:
            cmd_args.append("-hf")

        if device_info[CONF_VERTICAL_FLIP]:
            cmd_args.append("-vf")

        if device_info[CONF_OVERLAY_METADATA]:
            cmd_args.append("-a")
            cmd_args.append(str(device_info[CONF_OVERLAY_METADATA]))

        if device_info[CONF_OVERLAY_TIMESTAMP]:
            cmd_args.append("-a")
            cmd_args.append("4")
            cmd_args.append("-a")
            cmd_args.append(str(device_info[CONF_OVERLAY_TIMESTAMP]))

        subprocess.Popen(cmd_args, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    def camera_image(self):
        """Return raspistill image response."""
        with open(self._config[CONF_FILE_PATH], "rb") as file:
            return file.read()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def frame_interval(self):
        """Return the interval between frames of the stream."""
        return self._config[CONF_TIMELAPSE] / 1000
