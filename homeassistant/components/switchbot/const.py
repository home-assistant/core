"""Constants for the switchbot integration."""
DOMAIN = "switchbot"
MANUFACTURER = "switchbot"

# Config Attributes
ATTR_BOT = "bot"
ATTR_CURTAIN = "curtain"
ATTR_HYGROMETER = "hygrometer"
ATTR_CONTACT = "contact"
ATTR_PLUG = "plug"
DEFAULT_NAME = "Switchbot"
SUPPORTED_MODEL_TYPES = {
    "WoHand": ATTR_BOT,
    "WoCurtain": ATTR_CURTAIN,
    "WoSensorTH": ATTR_HYGROMETER,
    "WoContact": ATTR_CONTACT,
    "WoPlug": ATTR_PLUG,
}

# Config Defaults
DEFAULT_RETRY_COUNT = 3

# Config Options
CONF_RETRY_COUNT = "retry_count"

# Deprecated config Entry Options to be removed in 2023.4
CONF_TIME_BETWEEN_UPDATE_COMMAND = "update_time"
CONF_RETRY_TIMEOUT = "retry_timeout"
CONF_SCAN_TIMEOUT = "scan_timeout"
