"""Constants for Nuki."""
DOMAIN = "nuki"

# Attributes
ATTR_BATTERY_CRITICAL = "battery_critical"
ATTR_NUKI_ID = "nuki_id"
ATTR_UNLATCH = "unlatch"

# Data
DATA_BRIDGE = "nuki_bridge_data"
DATA_LOCKS = "nuki_locks_data"
DATA_OPENERS = "nuki_openers_data"
DATA_COORDINATOR = "nuki_coordinator"
ATTR_LOCK_DOORSENSOR_STATE = "doorSensorState"
ATTR_LOCK_DOORSENSOR_STATE_NAME = "doorSensorStateName"

# Defaults
DEFAULT_PORT = 8080
DEFAULT_TIMEOUT = 20

ERROR_STATES = (0, 254, 255)
