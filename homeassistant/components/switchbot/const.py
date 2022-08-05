"""Constants for the switchbot integration."""
from switchbot import SwitchbotModel

DOMAIN = "switchbot"
MANUFACTURER = "switchbot"

# Config Attributes

DEFAULT_NAME = "Switchbot"

SUPPORTED_MODEL_TYPES = {
    SwitchbotModel.BOT,
    SwitchbotModel.CURTAIN,
    SwitchbotModel.METER,
    SwitchbotModel.CONTACT_SENSOR,
    SwitchbotModel.PLUG_MINI,
    SwitchbotModel.MOTION_SENSOR,
    SwitchbotModel.COLOR_BULB,
}


# Config Defaults
DEFAULT_RETRY_COUNT = 3

# Config Options
CONF_RETRY_COUNT = "retry_count"

# Deprecated config Entry Options to be removed in 2023.4
CONF_TIME_BETWEEN_UPDATE_COMMAND = "update_time"
CONF_RETRY_TIMEOUT = "retry_timeout"
CONF_SCAN_TIMEOUT = "scan_timeout"
