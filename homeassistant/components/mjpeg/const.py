"""Constants for the MJPEG integration."""

import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "mjpeg"
PLATFORMS: Final = [Platform.CAMERA]

LOGGER = logging.getLogger(__package__)

CONF_MJPEG_URL: Final = "mjpeg_url"
CONF_STILL_IMAGE_URL: Final = "still_image_url"
