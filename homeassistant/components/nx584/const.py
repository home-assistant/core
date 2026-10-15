"""Constants for the NX584 integration."""

DOMAIN = "nx584"

CONF_EXCLUDE_ZONES = "exclude_zones"
CONF_PLATFORMS = "platforms"
CONF_ZONE_TYPES = "zone_types"

DEFAULT_HOST = "localhost"
DEFAULT_NAME = "NX584"
DEFAULT_PORT = 5007

# Bounds every request so a stalled server cannot block an executor thread.
REQUEST_TIMEOUT = 10
