"""LinkPlay constants."""

import logging
from typing import Final

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)
DOMAIN: Final = "linkplay"
PLATFORMS = [Platform.MEDIA_PLAYER]

DATA_SESSION: Final = "LinkPlaySession"
