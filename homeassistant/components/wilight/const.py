"""Constants for the WiLight integration."""

DOMAIN = "wilight"

DT_CONFIG = "config"
DT_REGISTRY = "registry"
DT_PENDING = "pending"
DT_SERIAL = "serialnumbers"

DEFAULT_RECONNECT_INTERVAL = 15
DEFAULT_KEEP_ALIVE_INTERVAL = 5
CONNECTION_TIMEOUT = 15

# Item types
ITEM_NONE = "none"
ITEM_LIGHT = "light"
ITEM_SWITCH = "switch"
ITEM_FAN = "fan"
ITEM_COVER = "cover"

# Light types
LIGHT_NONE = "none"
LIGHT_ON_OFF = "light_on_off"
LIGHT_DIMMER = "light_dimmer"
LIGHT_COLOR = "light_rgb"

# Switch types
SWITCH_NONE = "none"
SWITCH_V1 = "switch_v1"
SWITCH_VALVE = "switch_valve"
SWITCH_PAUSE_VALVE = "switch_pause_valve"

# Fan types
FAN_NONE = "none"
FAN_V1 = "fan_v1"

# Cover types
COVER_NONE = "none"
COVER_V1 = "cover_v1"

# Light service support
SUPPORT_NONE = 0

# Fan status
DIRECTION_OFF = "off"

# Cover commands
COVER_OPEN = "open"
COVER_CLOSE = "close"
COVER_STOP = "stop"

# Cover status
STATE_MOTOR_STOPPED = "stopped"
