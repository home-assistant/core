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
MIN_API_VERSION = "v19"


def api_version_number(api_version: str) -> int | None:
    """Return the numeric API version, if valid."""
    if not api_version.startswith("v"):
        return None
    try:
        return int(api_version[1:])
    except ValueError:
        return None


def is_supported_api_version(api_version: str) -> bool:
    """Return whether the API version is supported by the integration."""
    version = api_version_number(api_version)
    minimum_version = api_version_number(MIN_API_VERSION)
    return (
        version is not None
        and minimum_version is not None
        and version >= minimum_version
    )


UPDATE_INTERVAL = timedelta(seconds=10)

API_TIMEOUT = 10.0

VOLUME_MIN = 0
VOLUME_MAX = 255
VOLUME_STEP = 10

PLAYER_STATE_STOPPED = 1
PLAYER_STATE_PLAYING = 2
PLAYER_STATE_PAUSED = 3

MULTIROOM_GROUP_NAME = "Home Group"
SONGCAST_MODE_UNICAST = 0

# Songcast sender "state"
SENDER_STATE_STOPPED = 1
SENDER_STATE_PLAYING = 2

# Songcast receiver "state"
RECEIVER_STATE_OFF = 0
RECEIVER_STATE_NOT_PLAYING = 1
RECEIVER_STATE_PLAYING = 2
RECEIVER_STATE_DISCONNECTED = 3

LOGGER = logging.getLogger(__package__)
