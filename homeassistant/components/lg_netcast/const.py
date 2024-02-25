"""Constants for the lg_netcast component."""

from datetime import timedelta
from typing import Final

ATTR_MANUFACTURER: Final = "LG"
ATTR_MODEL_NAME = "model_name"
ATTR_FRIENDLY_NAME = "friendly_name"
ATTR_UUID = "uuid"

DEFAULT_NAME: Final = "LG Netcast TV"

DOMAIN = "lg_netcast"

DISPLAY_ACCESS_TOKEN_INTERVAL = timedelta(seconds=1)
