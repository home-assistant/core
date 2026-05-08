"""Constants used by the izone component."""

IZONE = "izone"

DATA_DISCOVERY_SERVICE = "izone_discovery"
DATA_CONFIG = "izone_config"

DISPATCH_CONTROLLER_DISCOVERED = "izone_controller_discovered"
DISPATCH_CONTROLLER_DISCONNECTED = "izone_controller_disconnected"
DISPATCH_CONTROLLER_RECONNECTED = "izone_controller_reconnected"
DISPATCH_CONTROLLER_UPDATE = "izone_controller_update"
DISPATCH_ZONE_UPDATE = "izone_zone_update"

TIMEOUT_DISCOVERY = 20
TIMEOUT_CONNECT = 10

# How often (seconds) to retry reconnecting static-IP controllers
# that have become disconnected. This replaces the broadcast-based
# reconnection that doesn't work across VLANs.
STATIC_RECONNECT_INTERVAL = 15

# Grace period (seconds) before marking a controller as unavailable.
# The pizone library triggers a disconnect on any single failed HTTP
# request (e.g., a 3-second timeout). This debounce prevents the
# entity from flapping between available/unavailable on transient
# network issues. The controller only shows as unavailable if it
# remains disconnected for this entire duration.
UNAVAILABLE_DEBOUNCE = 60

# Increased HTTP request timeout (seconds) for the pizone library.
# The default of 3 seconds is too aggressive for iZone controllers
# that may be slow to respond during HVAC operations.
REQUEST_TIMEOUT = 8
