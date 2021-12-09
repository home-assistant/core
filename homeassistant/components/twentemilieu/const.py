"""Constants for the Twente Milieu integration."""
from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "twentemilieu"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(hours=1)

CONF_POST_CODE = "post_code"
CONF_HOUSE_NUMBER = "house_number"
CONF_HOUSE_LETTER = "house_letter"
