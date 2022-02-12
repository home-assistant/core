"""Define constants for the Spotify integration."""

import logging

DOMAIN = "spotify"

LOGGER = logging.getLogger(__package__)

DATA_SPOTIFY_CLIENT = "spotify_client"
DATA_SPOTIFY_DEVICES = "spotify_devices"
DATA_SPOTIFY_ME = "spotify_me"
DATA_SPOTIFY_SESSION = "spotify_session"

SPOTIFY_SCOPES = [
    # Needed to be able to control playback
    "user-modify-playback-state",
    # Needed in order to read available devices
    "user-read-playback-state",
    # Needed to determine if the user has Spotify Premium
    "user-read-private",
    # Needed for media browsing
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-library-read",
    "user-top-read",
    "user-read-playback-position",
    "user-read-recently-played",
    "user-follow-read",
]

MEDIA_PLAYER_PREFIX = "spotify://"
