"""Support for Xiaomi Yeelight WiFi color bulb."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "yeelight"


STATE_CHANGE_TIME = 0.40  # seconds
POWER_STATE_CHANGE_TIME = 1  # seconds


#
# These models do not transition correctly when turning on, and
# yeelight is no longer updating the firmware on older devices
#
# https://github.com/home-assistant/core/issues/58315
#
# The problem can be worked around by always setting the brightness
# even when the bulb is reporting the brightness is already at the
# desired level.
#
MODELS_WITH_DELAYED_ON_TRANSITION = {
    "color",  # YLDP02YL
}

DATA_UPDATED = "yeelight_{}_data_updated"

DEFAULT_NAME = "Yeelight"
DEFAULT_TRANSITION = 350
DEFAULT_MODE_MUSIC = False
DEFAULT_SAVE_ON_CHANGE = False
DEFAULT_NIGHTLIGHT_SWITCH = False

CONF_DETECTED_MODEL = "detected_model"
CONF_TRANSITION = "transition"

CONF_SAVE_ON_CHANGE = "save_on_change"
CONF_MODE_MUSIC = "use_music_mode"
CONF_FLOW_PARAMS = "flow_params"
CONF_CUSTOM_EFFECTS = "custom_effects"
CONF_NIGHTLIGHT_SWITCH_TYPE = "nightlight_switch_type"
CONF_NIGHTLIGHT_SWITCH = "nightlight_switch"

DATA_CONFIG_ENTRIES = "config_entries"
DATA_CUSTOM_EFFECTS = "custom_effects"
DATA_DEVICE = "device"
DATA_REMOVE_INIT_DISPATCHER = "remove_init_dispatcher"
DATA_PLATFORMS_LOADED = "platforms_loaded"

ATTR_COUNT = "count"
ATTR_ACTION = "action"
ATTR_TRANSITIONS = "transitions"
ATTR_MODE_MUSIC = "music_mode"

ACTION_RECOVER = "recover"
ACTION_STAY = "stay"
ACTION_OFF = "off"

ACTIVE_MODE_NIGHTLIGHT = 1
ACTIVE_COLOR_FLOWING = 1


NIGHTLIGHT_SWITCH_TYPE_LIGHT = "light"

DISCOVERY_INTERVAL = timedelta(seconds=60)
SSDP_TARGET = ("239.255.255.250", 1982)
SSDP_ST = "wifi_bulb"
DISCOVERY_ATTEMPTS = 3
DISCOVERY_SEARCH_INTERVAL = timedelta(seconds=2)
DISCOVERY_TIMEOUT = 8


YEELIGHT_RGB_TRANSITION = "RGBTransition"
YEELIGHT_HSV_TRANSACTION = "HSVTransition"
YEELIGHT_TEMPERATURE_TRANSACTION = "TemperatureTransition"
YEELIGHT_SLEEP_TRANSACTION = "SleepTransition"


UPDATE_REQUEST_PROPERTIES = [
    "power",
    "main_power",
    "bright",
    "ct",
    "rgb",
    "hue",
    "sat",
    "color_mode",
    "flowing",
    "bg_power",
    "bg_lmode",
    "bg_flowing",
    "bg_ct",
    "bg_bright",
    "bg_hue",
    "bg_sat",
    "bg_rgb",
    "nl_br",
    "active_mode",
]


PLATFORMS = [Platform.BINARY_SENSOR, Platform.LIGHT]
