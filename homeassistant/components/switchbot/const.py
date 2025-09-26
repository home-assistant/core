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
    REMOTE = "remote"
    ROLLER_SHADE = "roller_shade"
    HUBMINI_MATTER = "hubmini_matter"
    CIRCULATOR_FAN = "circulator_fan"
    K20_VACUUM = "k20_vacuum"
    S10_VACUUM = "s10_vacuum"
    K10_VACUUM = "k10_vacuum"
    K10_PRO_VACUUM = "k10_pro_vacuum"
    K10_PRO_COMBO_VACUUM = "k10_pro_combo_vacumm"
    HUB3 = "hub3"
    LOCK_LITE = "lock_lite"
    LOCK_ULTRA = "lock_ultra"
    AIR_PURIFIER = "air_purifier"
    AIR_PURIFIER_TABLE = "air_purifier_table"
    EVAPORATIVE_HUMIDIFIER = "evaporative_humidifier"
    FLOOR_LAMP = "floor_lamp"
    STRIP_LIGHT_3 = "strip_light_3"
    RGBICWW_STRIP_LIGHT = "rgbicww_strip_light"
    RGBICWW_FLOOR_LAMP = "rgbicww_floor_lamp"
    PLUG_MINI_EU = "plug_mini_eu"
    RELAY_SWITCH_2PM = "relay_switch_2pm"
    K11_PLUS_VACUUM = "k11+_vacuum"


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
    SwitchbotModel.ROLLER_SHADE: SupportedModels.ROLLER_SHADE,
    SwitchbotModel.CIRCULATOR_FAN: SupportedModels.CIRCULATOR_FAN,
    SwitchbotModel.K20_VACUUM: SupportedModels.K20_VACUUM,
    SwitchbotModel.S10_VACUUM: SupportedModels.S10_VACUUM,
    SwitchbotModel.K10_VACUUM: SupportedModels.K10_VACUUM,
    SwitchbotModel.K10_PRO_VACUUM: SupportedModels.K10_PRO_VACUUM,
    SwitchbotModel.K10_PRO_COMBO_VACUUM: SupportedModels.K10_PRO_COMBO_VACUUM,
    SwitchbotModel.LOCK_LITE: SupportedModels.LOCK_LITE,
    SwitchbotModel.LOCK_ULTRA: SupportedModels.LOCK_ULTRA,
    SwitchbotModel.AIR_PURIFIER: SupportedModels.AIR_PURIFIER,
    SwitchbotModel.AIR_PURIFIER_TABLE: SupportedModels.AIR_PURIFIER_TABLE,
    SwitchbotModel.EVAPORATIVE_HUMIDIFIER: SupportedModels.EVAPORATIVE_HUMIDIFIER,
    SwitchbotModel.FLOOR_LAMP: SupportedModels.FLOOR_LAMP,
    SwitchbotModel.STRIP_LIGHT_3: SupportedModels.STRIP_LIGHT_3,
    SwitchbotModel.RGBICWW_STRIP_LIGHT: SupportedModels.RGBICWW_STRIP_LIGHT,
    SwitchbotModel.RGBICWW_FLOOR_LAMP: SupportedModels.RGBICWW_FLOOR_LAMP,
    SwitchbotModel.PLUG_MINI_EU: SupportedModels.PLUG_MINI_EU,
    SwitchbotModel.RELAY_SWITCH_2PM: SupportedModels.RELAY_SWITCH_2PM,
    SwitchbotModel.K11_VACUUM: SupportedModels.K11_PLUS_VACUUM,
}

NON_CONNECTABLE_SUPPORTED_MODEL_TYPES = {
    SwitchbotModel.METER: SupportedModels.HYGROMETER,
    SwitchbotModel.IO_METER: SupportedModels.HYGROMETER,
    SwitchbotModel.METER_PRO: SupportedModels.HYGROMETER,
    SwitchbotModel.METER_PRO_C: SupportedModels.HYGROMETER_CO2,
    SwitchbotModel.CONTACT_SENSOR: SupportedModels.CONTACT,
    SwitchbotModel.MOTION_SENSOR: SupportedModels.MOTION,
    SwitchbotModel.LEAK: SupportedModels.LEAK,
    SwitchbotModel.REMOTE: SupportedModels.REMOTE,
    SwitchbotModel.HUBMINI_MATTER: SupportedModels.HUBMINI_MATTER,
    SwitchbotModel.HUB3: SupportedModels.HUB3,
}

SUPPORTED_MODEL_TYPES = (
    CONNECTABLE_SUPPORTED_MODEL_TYPES | NON_CONNECTABLE_SUPPORTED_MODEL_TYPES
)

ENCRYPTED_MODELS = {
    SwitchbotModel.RELAY_SWITCH_1,
    SwitchbotModel.RELAY_SWITCH_1PM,
    SwitchbotModel.LOCK,
    SwitchbotModel.LOCK_PRO,
    SwitchbotModel.LOCK_LITE,
    SwitchbotModel.LOCK_ULTRA,
    SwitchbotModel.AIR_PURIFIER,
    SwitchbotModel.AIR_PURIFIER_TABLE,
    SwitchbotModel.EVAPORATIVE_HUMIDIFIER,
    SwitchbotModel.FLOOR_LAMP,
    SwitchbotModel.STRIP_LIGHT_3,
    SwitchbotModel.RGBICWW_STRIP_LIGHT,
    SwitchbotModel.RGBICWW_FLOOR_LAMP,
    SwitchbotModel.PLUG_MINI_EU,
    SwitchbotModel.RELAY_SWITCH_2PM,
}

ENCRYPTED_SWITCHBOT_MODEL_TO_CLASS: dict[
    SwitchbotModel, switchbot.SwitchbotEncryptedDevice
] = {
    SwitchbotModel.LOCK: switchbot.SwitchbotLock,
    SwitchbotModel.LOCK_PRO: switchbot.SwitchbotLock,
    SwitchbotModel.RELAY_SWITCH_1PM: switchbot.SwitchbotRelaySwitch,
    SwitchbotModel.RELAY_SWITCH_1: switchbot.SwitchbotRelaySwitch,
    SwitchbotModel.LOCK_LITE: switchbot.SwitchbotLock,
    SwitchbotModel.LOCK_ULTRA: switchbot.SwitchbotLock,
    SwitchbotModel.AIR_PURIFIER: switchbot.SwitchbotAirPurifier,
    SwitchbotModel.AIR_PURIFIER_TABLE: switchbot.SwitchbotAirPurifier,
    SwitchbotModel.EVAPORATIVE_HUMIDIFIER: switchbot.SwitchbotEvaporativeHumidifier,
    SwitchbotModel.FLOOR_LAMP: switchbot.SwitchbotStripLight3,
    SwitchbotModel.STRIP_LIGHT_3: switchbot.SwitchbotStripLight3,
    SwitchbotModel.RGBICWW_STRIP_LIGHT: switchbot.SwitchbotRgbicLight,
    SwitchbotModel.RGBICWW_FLOOR_LAMP: switchbot.SwitchbotRgbicLight,
    SwitchbotModel.PLUG_MINI_EU: switchbot.SwitchbotRelaySwitch,
    SwitchbotModel.RELAY_SWITCH_2PM: switchbot.SwitchbotRelaySwitch2PM,
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
