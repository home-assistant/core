# noqa: ignore=all

"""
Constants for the Spotify component.
"""

import logging
from homeassistant.components.media_player import MediaType

DOMAIN = "spotify"
""" Domain identifier for this integration. """

DOMAIN_SCRIPT = "script"
""" Domain identifier for script integration. """

LOGGER = logging.getLogger(__package__)

CONF_OPTION_DEVICE_DEFAULT = "device_default"
CONF_OPTION_DEVICE_LOGINID = "device_loginid"
CONF_OPTION_DEVICE_PASSWORD = "device_password"
CONF_OPTION_DEVICE_USERNAME = "device_username"
CONF_OPTION_SCRIPT_TURN_ON = "script_turn_on"
CONF_OPTION_SCRIPT_TURN_OFF = "script_turn_off"
CONF_OPTION_SOURCE_LIST_HIDE = "source_list_hide"

# security scopes required by various Spotify Web API endpoints.
SPOTIFY_SCOPES: list = [
    "playlist-modify-private",
    "playlist-modify-public",
    "playlist-read-collaborative",
    "playlist-read-private",
    "ugc-image-upload",
    "user-follow-modify",
    "user-follow-read",
    "user-library-modify",
    "user-library-read",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "user-read-email",
    "user-read-playback-position",
    "user-read-playback-state",
    "user-read-private",
    "user-read-recently-played",
    "user-top-read",
]

TRACE_MSG_DELAY_DEVICE_SONOS: str = (
    "Delaying for %s seconds to allow Sonos Soco API to process the change"
)
"""
Delaying for %s seconds to allow Sonos Soco API to process the change
"""
