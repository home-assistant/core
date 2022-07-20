"""Constants for the switchbot integration."""
DOMAIN = "switchbot"
MANUFACTURER = "switchbot"

# Config Attributes
ATTR_BOT = "bot"
ATTR_CURTAIN = "curtain"
DEFAULT_NAME = "Switchbot"
SUPPORTED_MODEL_TYPES = {"WoHand": ATTR_BOT, "WoCurtain": ATTR_CURTAIN}

# Config Defaults
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_TIMEOUT = 5
DEFAULT_TIME_BETWEEN_UPDATE_COMMAND = 60
DEFAULT_SCAN_TIMEOUT = 5

# Config Options
CONF_TIME_BETWEEN_UPDATE_COMMAND = "update_time"
CONF_RETRY_COUNT = "retry_count"
CONF_RETRY_TIMEOUT = "retry_timeout"
CONF_SCAN_TIMEOUT = "scan_timeout"

# Data
DATA_COORDINATOR = "coordinator"
COMMON_OPTIONS = "common_options"
