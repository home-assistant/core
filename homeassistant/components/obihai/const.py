"""Constants for the Obihai integration."""

import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "obihai"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"
OBIHAI = "Obihai"

LOGGER = logging.getLogger(__package__)

PLATFORMS: Final = [Platform.BUTTON, Platform.SENSOR]
