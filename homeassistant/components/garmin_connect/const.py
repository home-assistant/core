"""Constants for Garmin Connect integration."""

from typing import Final

DOMAIN: Final = "garmin_connect"

# Config entry keys
CONF_OAUTH1_TOKEN: Final = "oauth1_token"
CONF_OAUTH2_TOKEN: Final = "oauth2_token"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Default values
DEFAULT_SCAN_INTERVAL: Final = 300  # 5 minutes
MIN_SCAN_INTERVAL: Final = 60  # 1 minute
MAX_SCAN_INTERVAL: Final = 3600  # 1 hour
