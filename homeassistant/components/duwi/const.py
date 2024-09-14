"""Constants for the DUWI integration."""

from enum import StrEnum
import logging

from homeassistant.const import Platform

_LOGGER = logging.getLogger(__package__)

MANUFACTURER = "duwi"

DOMAIN = "duwi"

APP_VERSION = "0.1.1"

CLIENT_VERSION = "0.1.1"

CLIENT_MODEL = "homeassistant"

DUWI_DISCOVERY_NEW = "duwi_discovery_new"
DUWI_SCENE_UPDATE = "duwi_scene_update"
DUWI_HA_SIGNAL_UPDATE_ENTITY = "duwi_entry_update"
DUWI_HA_ACCESS_TOKEN = "duwi_access_token"

# API keys
CLIENT = "client"
ADDRESS = "address"
WS_ADDRESS = "ws_address"
APP_KEY = "app_key"
APP_SECRET = "app_secret"
ACCESS_TOKEN = "access_token"
REFRESH_TOKEN = "refresh_token"
PHONE = "phone"
PASSWORD = "password"
HOUSE_NO = "house_no"
HOUSE_NAME = "house_name"
HOUSE_KEY = "house_key"
CONF_TOKEN_INFO = "token_info"

# List of platforms that support config entry
SUPPORTED_PLATFORMS = [
    Platform.SWITCH,
]


class DPCode(StrEnum):
    """Data Point Codes used by Duwi."""

    # button
    BUTTON = "button"

    # switch
    SWITCH = "switch"

    # light
    ON_OFF = "on_off"
    LIGHT = "light"
    COLOR_TEMP = "color_temp"
    COLOR = "color"
    RGB = "rgb"
    RGBW = "rgbw"
    RGBCW = "rgbcw"

    # cover
    ROLLER = "roller"
    SHUTTER = "shutter"
    SHUTTER_2 = "shutter-2"

    # music
    HUA_ERSI_MUSIC = "hua_ersi_music"
    XIANG_WANG_MUSIC_S7_MINI_3S = "xiangwang_music_s7_mini_3s"
    XIANG_WANG_MUSIC_S8 = "xiangwang_music_s8"
    SHENG_BI_KE_MUSIC = "sheng_bike_music"
    BO_SHENG_MUSIC = "bo_sheng_music"
    YOU_DA_MUSIC = "youda_music"

    # sensor
    TEMP = "temp"
    HUMIDITY = "humidity"
    HCHO = "hcho"
    PM25 = "pm25"
    CO2 = "co2"
    BRIGHT = "bright"
    IQA = "iaq"
    HUMAN = "human"
    TRIGGER = "trigger"
    MOISTURE = "moisture"
    SMOKE = "smoke"
    MOVING = "moving"
    GAS = "gas"
    DOOR = "door"
    OPENING = "opening"
    CO = "co"
    TVOC = "tvoc"
    PM10 = "pm10"

    # climate
    AC = "ac"
    FA = "fa"
    FH = "fh"
    HP = "hp"
    TC = "tc"
