"""Constants for the switchbot integration."""

from enum import StrEnum

import switchbot
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
    HYGROMETER_CO2 = "hygrometer_co2"
    LIGHT_STRIP = "light_strip"
    CONTACT = "contact"
    PLUG = "plug"
    MOTION = "motion"
    HUMIDIFIER = "humidifier"
    LOCK = "lock"
    LOCK_PRO = "lock_pro"
    BLIND_TILT = "blind_tilt"
    HUB2 = "hub2"
    RELAY_SWITCH_1PM = "relay_switch_1pm"
    RELAY_SWITCH_1 = "relay_switch_1"
    LEAK = "leak"


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
    SwitchbotModel.RELAY_SWITCH_1PM: SupportedModels.RELAY_SWITCH_1PM,
    SwitchbotModel.RELAY_SWITCH_1: SupportedModels.RELAY_SWITCH_1,
}

NON_CONNECTABLE_SUPPORTED_MODEL_TYPES = {
    SwitchbotModel.METER: SupportedModels.HYGROMETER,
    SwitchbotModel.IO_METER: SupportedModels.HYGROMETER,
    SwitchbotModel.METER_PRO: SupportedModels.HYGROMETER,
    SwitchbotModel.METER_PRO_C: SupportedModels.HYGROMETER_CO2,
    SwitchbotModel.CONTACT_SENSOR: SupportedModels.CONTACT,
    SwitchbotModel.MOTION_SENSOR: SupportedModels.MOTION,
    SwitchbotModel.LEAK: SupportedModels.LEAK,
}

SUPPORTED_MODEL_TYPES = (
    CONNECTABLE_SUPPORTED_MODEL_TYPES | NON_CONNECTABLE_SUPPORTED_MODEL_TYPES
)

ENCRYPTED_MODELS = {
    SwitchbotModel.RELAY_SWITCH_1,
    SwitchbotModel.RELAY_SWITCH_1PM,
    SwitchbotModel.LOCK,
    SwitchbotModel.LOCK_PRO,
}

ENCRYPTED_SWITCHBOT_MODEL_TO_CLASS: dict[
    SwitchbotModel, switchbot.SwitchbotEncryptedDevice
] = {
    SwitchbotModel.LOCK: switchbot.SwitchbotLock,
    SwitchbotModel.LOCK_PRO: switchbot.SwitchbotLock,
    SwitchbotModel.RELAY_SWITCH_1PM: switchbot.SwitchbotRelaySwitch,
    SwitchbotModel.RELAY_SWITCH_1: switchbot.SwitchbotRelaySwitch,
}

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
