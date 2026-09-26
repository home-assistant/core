"""Constants for the AirLino integration."""

from datetime import timedelta
import logging

DOMAIN = "airlino"

VALID_MODELS = {
    "AirLino pro",
    "AirLino",
    "AirLino plus",
    "Airlino max",
}

DEFAULT_PORT = 8989

DEFAULT_API_VERSION = "v22"

UPDATE_INTERVAL = timedelta(seconds=10)

API_TIMEOUT = 10.0

VOLUME_MAX = 255

PLAYER_STATE_STOPPED = 1
PLAYER_STATE_PLAYING = 2
PLAYER_STATE_PAUSED = 3

MULTIROOM_GROUP_NAME = "Home Group"

# Songcast sender "state"
SENDER_STATE_STOPPED = 1
SENDER_STATE_PLAYING = 2

# Songcast receiver "state"
RECEIVER_STATE_OFF = 0
RECEIVER_STATE_NOT_PLAYING = 1
RECEIVER_STATE_PLAYING = 2
RECEIVER_STATE_DISCONNECTED = 3

LOGGER = logging.getLogger(__package__)
