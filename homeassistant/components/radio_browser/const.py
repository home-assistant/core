"""Constants for the Radio Browser integration."""
import logging
from typing import Final

DOMAIN: Final = "radio_browser"

LOGGER = logging.getLogger(__package__)
CONF_FAVORITE_RADIOS = "favorites"
CONF_RADIO_BROWSER = "radio_browser"
LAST_FAVORITE = "last_favorite_selected"

SERVICE_START_RADIO = "start_radio"
SERVICE_NEXT_RADIO = "next_radio"
SERVICE_PREV_RADIO = "prev_radio"
