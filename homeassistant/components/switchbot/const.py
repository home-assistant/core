"""Constants for the switchbot integration."""

from enum import StrEnum

from switchbot import SwitchbotModel

DOMAIN = "switchbot"
MANUFACTURER = "switchbot"

# Config Attributes

DEFAULT_NAME = "Switchbot"


class SupportedModels(StrEnum):
    """Supported Switchbot models."""

    BOT = "bot"
    BULB = "bulb"
    CEILING_LIGHT = "ceiling_light"
    CURTAIN = "curtain"
    HYGROMETER = "hygrometer"
    LIGHT_STRIP = "light_strip"
    CONTACT = "contact"
    PLUG = "plug"
    MOTION = "motion"
    HUMIDIFIER = "humidifier"
    LOCK = "lock"
    LOCK_PRO = "lock_pro"
    BLIND_TILT = "blind_tilt"
    HUB2 = "hub2"


CONNECTABLE_SUPPORTED_MODEL_TYPES = {
    SwitchbotModel.BOT: SupportedModels.BOT,
    SwitchbotModel.CURTAIN: SupportedModels.CURTAIN,
    SwitchbotModel.PLUG_MINI: SupportedModels.PLUG,
    SwitchbotModel.COLOR_BULB: SupportedModels.BULB,
    SwitchbotModel.LIGHT_STRIP: SupportedModels.LIGHT_STRIP,
    SwitchbotModel.CEILING_LIGHT: SupportedModels.CEILING_LIGHT,
    SwitchbotModel.HUMIDIFIER: SupportedModels.HUMIDIFIER,
    SwitchbotModel.LOCK: SupportedModels.LOCK,
    SwitchbotModel.LOCK_PRO: SupportedModels.LOCK_PRO,
    SwitchbotModel.BLIND_TILT: SupportedModels.BLIND_TILT,
    SwitchbotModel.HUB2: SupportedModels.HUB2,
}

NON_CONNECTABLE_SUPPORTED_MODEL_TYPES = {
    SwitchbotModel.METER: SupportedModels.HYGROMETER,
    SwitchbotModel.IO_METER: SupportedModels.HYGROMETER,
    SwitchbotModel.CONTACT_SENSOR: SupportedModels.CONTACT,
    SwitchbotModel.MOTION_SENSOR: SupportedModels.MOTION,
}

SUPPORTED_MODEL_TYPES = (
    CONNECTABLE_SUPPORTED_MODEL_TYPES | NON_CONNECTABLE_SUPPORTED_MODEL_TYPES
)

SUPPORTED_LOCK_MODELS = {SwitchbotModel.LOCK, SwitchbotModel.LOCK_PRO}

HASS_SENSOR_TYPE_TO_SWITCHBOT_MODEL = {
    str(v): k for k, v in SUPPORTED_MODEL_TYPES.items()
}

# Config Defaults
DEFAULT_RETRY_COUNT = 3
DEFAULT_LOCK_NIGHTLATCH = False

# Config Options
CONF_RETRY_COUNT = "retry_count"
CONF_KEY_ID = "key_id"
CONF_ENCRYPTION_KEY = "encryption_key"
CONF_LOCK_NIGHTLATCH = "lock_force_nightlatch"

# Deprecated config Entry Options to be removed in 2023.4
CONF_TIME_BETWEEN_UPDATE_COMMAND = "update_time"
CONF_RETRY_TIMEOUT = "retry_timeout"
CONF_SCAN_TIMEOUT = "scan_timeout"
