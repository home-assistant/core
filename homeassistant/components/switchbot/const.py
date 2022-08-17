"""Constants for the switchbot integration."""
from switchbot import SwitchbotModel

from homeassistant.backports.enum import StrEnum

DOMAIN = "switchbot"
MANUFACTURER = "switchbot"

# Config Attributes

DEFAULT_NAME = "Switchbot"


class SupportedModels(StrEnum):
    """Supported Switchbot models."""

    BOT = "bot"
    BULB = "bulb"
    CURTAIN = "curtain"
    HYGROMETER = "hygrometer"
    CONTACT = "contact"
    PLUG = "plug"
    MOTION = "motion"


SUPPORTED_MODEL_TYPES = {
    SwitchbotModel.BOT: SupportedModels.BOT,
    SwitchbotModel.CURTAIN: SupportedModels.CURTAIN,
    SwitchbotModel.METER: SupportedModels.HYGROMETER,
    SwitchbotModel.CONTACT_SENSOR: SupportedModels.CONTACT,
    SwitchbotModel.PLUG_MINI: SupportedModels.PLUG,
    SwitchbotModel.MOTION_SENSOR: SupportedModels.MOTION,
    SwitchbotModel.COLOR_BULB: SupportedModels.BULB,
}


# Config Defaults
DEFAULT_RETRY_COUNT = 3

# Config Options
CONF_RETRY_COUNT = "retry_count"

# Deprecated config Entry Options to be removed in 2023.4
CONF_TIME_BETWEEN_UPDATE_COMMAND = "update_time"
CONF_RETRY_TIMEOUT = "retry_timeout"
CONF_SCAN_TIMEOUT = "scan_timeout"
