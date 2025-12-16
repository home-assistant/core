"""Constants for the Transport NSW integration."""

DOMAIN = "transport_nsw"

# Configuration constants
CONF_STOP_ID = "stop_id"
CONF_ROUTE = "route"
CONF_DESTINATION = "destination"

# Subentry constants
SUBENTRY_TYPE_STOP = "stop"

# Attribute constants
ATTR_STOP_ID = "stop_id"
ATTR_ROUTE = "route"
ATTR_DUE_IN = "due"
ATTR_DELAY = "delay"
ATTR_REAL_TIME = "real_time"
ATTR_DESTINATION = "destination"

# Default values
DEFAULT_NAME = "Transport NSW"
DEFAULT_STOP_NAME = "Transport NSW Stop"

# Transport mode icons
TRANSPORT_ICONS = {
    "Train": "mdi:train",
    "Lightrail": "mdi:tram",
    "Bus": "mdi:bus",
    "Coach": "mdi:bus",
    "Ferry": "mdi:ferry",
    "Schoolbus": "mdi:bus",
    "n/a": "mdi:clock",
    None: "mdi:clock",
}
