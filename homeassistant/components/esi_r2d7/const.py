"""Constants for the ESI R2D7 integration."""

import logging

from esi_r2d7 import R2D7Connection

from homeassistant.config_entries import ConfigEntry

LOGGER = logging.getLogger(__package__)
DOMAIN = "esi_r2d7"

CONF_SYSTEM = "system"
CONF_FIRST_CHANNEL = "first_channel"
CONF_LAST_CHANNEL = "last_channel"

# The controller reports nothing back. A Stop is universal, so it marks as
# unknown the blind it was pressed on plus every blind sent Open or Close
# within this many seconds.
RECENT_MOVE_SECONDS = 120

type R2D7ConfigEntry = ConfigEntry[R2D7Connection]


def redact_port(port: str) -> str:
    """Return the port without its query string.

    An ESPHome proxy URL can carry the API key in its query string.
    """
    return port.split("?", 1)[0]
