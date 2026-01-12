"""Constants for the Unraid integration."""

from typing import Final

DOMAIN: Final = "unraid"
MANUFACTURER: Final = "Lime Technology"

# Default polling interval (seconds)
DEFAULT_SYSTEM_POLL_INTERVAL: Final = 30

# Network port configuration
CONF_HTTP_PORT: Final = "http_port"
CONF_HTTPS_PORT: Final = "https_port"
DEFAULT_HTTP_PORT: Final = 80
DEFAULT_HTTPS_PORT: Final = 443
