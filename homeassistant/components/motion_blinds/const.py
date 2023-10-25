"""Constants for the Motion Blinds component."""
from homeassistant.const import Platform

DOMAIN = "motion_blinds"
MANUFACTURER = "Motion Blinds, Coulisse B.V."
DEFAULT_GATEWAY_NAME = "Motion Blinds Gateway"

PLATFORMS = [Platform.COVER, Platform.SENSOR]

CONF_WAIT_FOR_PUSH = "wait_for_push"
CONF_INTERFACE = "interface"
DEFAULT_WAIT_FOR_PUSH = False
DEFAULT_INTERFACE = "any"

KEY_GATEWAY = "gateway"
KEY_API_LOCK = "api_lock"
KEY_COORDINATOR = "coordinator"
KEY_MULTICAST_LISTENER = "multicast_listener"
KEY_SETUP_LOCK = "setup_lock"
KEY_UNSUB_STOP = "unsub_stop"

ATTR_WIDTH = "width"
ATTR_ABSOLUTE_POSITION = "absolute_position"
ATTR_AVAILABLE = "available"

SERVICE_SET_ABSOLUTE_POSITION = "set_absolute_position"

UPDATE_INTERVAL = 600
UPDATE_INTERVAL_FAST = 60
UPDATE_DELAY_STOP = 3
UPDATE_INTERVAL_MOVING = 5
UPDATE_INTERVAL_MOVING_WIFI = 45
