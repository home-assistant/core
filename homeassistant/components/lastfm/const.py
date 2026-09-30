"""Constants for LastFM."""

import logging
from typing import Final

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)
DOMAIN: Final = "lastfm"
PLATFORMS = [Platform.SENSOR]
DEFAULT_NAME = "LastFM"

CONF_API_SECRET = "api_secret"
CONF_MAIN_USER = "main_user"
CONF_SESSION_KEY = "session_key"
CONF_USERS = "users"

POLLING_INTERVAL = 2
MAX_POLLING_ATTEMPTS = 60

# Last.fm API error returned when a user hides their recent listening information
ERROR_CODE_LOGIN_REQUIRED = "17"
ERROR_CODE_INVALID_SESSION_KEY = "9"
ERROR_CODE_TOKEN_UNAUTHORIZED = "14"
ERROR_CODES_INVALID_AUTH = {"4", "10", "13", "26"}
ERROR_CODES_RETRYABLE = {"8", "11", "16", "29", "500", "502", "503", "504"}

ATTR_LAST_PLAYED = "last_played"
ATTR_PLAY_COUNT = "play_count"
ATTR_TOP_PLAYED = "top_played"

STATE_NOT_SCROBBLING = "Not Scrobbling"
