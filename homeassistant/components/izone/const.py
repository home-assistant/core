"""Constants used by the izone component."""

DOMAIN = "izone"

DATA_DISCOVERY_SERVICE = "izone_discovery"
DATA_CONFIG = "izone_config"

DISPATCH_CONTROLLER_DISCOVERED = "izone_controller_discovered"
DISPATCH_CONTROLLER_DISCONNECTED = "izone_controller_disconnected"
DISPATCH_CONTROLLER_RECONNECTED = "izone_controller_reconnected"
DISPATCH_CONTROLLER_UPDATE = "izone_controller_update"
DISPATCH_ZONE_UPDATE = "izone_zone_update"

TIMEOUT_DISCOVERY = 5
DISCOVERY_IDLE_SECONDS = 4 * TIMEOUT_DISCOVERY

# Config entry data key: host explicitly entered by the user during manual setup.
# Discovery-sourced addresses are runtime state and are not persisted in entries.
CONF_USER_CONFIGURED_HOST = "user_configured_host"
