"""Constants for the everHome integration."""

from typing import Final

DOMAIN = "everhome"

CONF_FAST_POLLING: Final = "fast_polling"

# Default values
DEFAULT_UPDATE_INTERVAL = 5  # seconds
FAST_UPDATE_INTERVAL = 1  # seconds

# Device attributes
ATTR_MANUFACTURER = "everHome"
ATTR_MODEL = "EcoTracker"
