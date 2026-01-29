"""Constants for the Unraid integration."""

from typing import Final

DOMAIN: Final = "unraid"
MANUFACTURER: Final = "Lime Technology"

# Default HTTP port - the unraid-api library handles SSL detection
# and myunraid.net Strict mode redirects automatically
DEFAULT_PORT: Final = 80
