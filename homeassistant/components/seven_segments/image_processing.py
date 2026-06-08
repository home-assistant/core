"""Optical character recognition processing of seven segments displays."""

import io
import logging
import os
import subprocess

from PIL import Image
import voluptuous as vol

from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA as IMAGE_PROCESSING_PLATFORM_SCHEMA,
    ImageProcessingDeviceClass,
    ImageProcessingEntity,
)
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, CONF_SOURCE
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_DIGITS = "digits"
CONF_EXTRA_ARGUMENTS = "extra_arguments"
CONF_HEIGHT = "height"
CONF_ROTATE = "rotate"
CONF_SSOCR_BIN = "ssocr_bin"
CONF_THRESHOLD = "threshold"
CONF_WIDTH = "width"
CONF_X_POS = "x_position"
CONF_Y_POS = "y_position"
CONF_WRITE_FILE = "write_file"
CONF_DEBUG_IMAGE = "debug_image"

DEFAULT_BINARY = "ssocr"

PLATFORM_SCHEMA = IMAGE_PROCESSING_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_EXTRA_ARGUMENTS, default=""): cv.string,
        vol.Optional(CONF_DIGITS): cv.positive_int,
        vol.Optional(CONF_HEIGHT, default=0): cv.positive_int,
        vol.Optional(CONF_SSOCR_BIN, default=DEFAULT_BINARY): cv.string,
        vol.Optional(CONF_THRESHOLD, default=0): cv.positive_int,
        vol.Optional(CONF_ROTATE, default=0): cv.positive_int,
        vol.Optional(CONF_WIDTH, default=0): cv.positive_int,
        vol.Optional(CONF_X_POS, default=0): cv.string,
        vol.Optional(CONF_Y_POS, default=0): cv.positive_int,
        vol.Optional(CONF_WRITE_FILE, default=True): cv.boolean,
        vol.Optional(CONF_DEBUG_IMAGE, default=False): cv.boolean,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Seven segments OCR platform."""
    async_add_entities(
        ImageProcessingSsocr(
            hass, camera[CONF_ENTITY_ID], config, camera.get(CONF_NAME)
        )
        for camera in config[CONF_SOURCE]
    )


class ImageProcessingSsocr(ImageProcessingEntity):
    """Representation of the seven segments OCR image processing entity."""

    _attr_device_class = ImageProcessingDeviceClass.OCR

    def __init__(
        self,
        hass: HomeAssistant,
        camera_entity: str,
        config: ConfigType,
        name: str | None,
    ) -> None:
        """Initialize seven segments processing."""
        self._attr_camera_entity = camera_entity
        if name:
            self._attr_name = name
        else:
            self._attr_name = f"SevenSegment OCR {split_entity_id(camera_entity)[1]}"
        self._attr_state = None

        self._write_file = config[CONF_WRITE_FILE]
        self._debug_image = config[CONF_DEBUG_IMAGE]

        safe_name = self._attr_name.replace(" ", "_")
        self.filepath = os.path.join(
            hass.config.config_dir,
            f"ssocr-{safe_name}.png",
        )
        self.debug_filepath = os.path.join(
            hass.config.config_dir,
            f"ssocr-debug-{safe_name}.png",
        )

        crop = [
            "crop",
            str(config[CONF_X_POS]),
            str(config[CONF_Y_POS]),
            str(config[CONF_WIDTH]),
            str(config[CONF_HEIGHT]),
        ]
        digits = ["-d", str(config.get(CONF_DIGITS, -1))]
        rotate = ["rotate", str(config[CONF_ROTATE])]
        threshold = ["-t", str(config[CONF_THRESHOLD])]
        extra_arguments = config[CONF_EXTRA_ARGUMENTS].split(" ")

        self._command = [
            config[CONF_SSOCR_BIN],
            *crop,
            *digits,
            *threshold,
            *rotate,
            *extra_arguments,
        ]

        if self._debug_image:
            self._command.append(f"--debug-image={self.debug_filepath}")

        if self._write_file:
            self._command.append(self.filepath)
        else:
            self._command.append("-")

    def process_image(self, image: bytes) -> None:
        """Process the image."""
        input_data = None

        with io.BytesIO(image) as stream, Image.open(stream) as img:
            if self._write_file:
                img.save(self.filepath, "png")
            else:
                with io.BytesIO() as out_stream:
                    img.save(out_stream, "png")
                    input_data = out_stream.getvalue()

        with subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE if not self._write_file else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=False,  # Required for posix_spawn
        ) as ocr:
            out = ocr.communicate(input=input_data)
            if out[0] != b"":
                self._attr_state = out[0].strip().decode("utf-8")
            else:
                self._attr_state = None
                _LOGGER.warning(
                    "Unable to detect value: %s", out[1].strip().decode("utf-8")
                )
