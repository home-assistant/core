"""Constants for LastFM."""
import logging
from typing import Final

LOGGER = logging.getLogger(__package__)
DOMAIN: Final = "lastfm"
DEFAULT_NAME = "LastFM"

CONF_USERS = "users"

ATTR_LAST_PLAYED = "last_played"
ATTR_PLAY_COUNT = "play_count"
ATTR_TOP_PLAYED = "top_played"

STATE_NOT_SCROBBLING = "Not Scrobbling"
