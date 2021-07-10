"""Constants for the STIHL iMow integration."""
from enum import Enum

API_UPDATE_INTERVALL_SECONDS = 120
API_DEFAULT_LANGUAGE = "English"
API_UPDATE_TIMEOUT = 20

DOMAIN = "stihl_imow"
CONF_MOWER_IDENTIFIER = "mower_id"
CONF_MOWER = "mower"
CONF_MOWER_VERSION = "version"
CONF_MOWER_MODEL = "deviceTypeDescription"
IMOW_MOWER_CONFIG = "mower_config"
CONF_API_TOKEN = "token"
CONF_API_TOKEN_EXPIRE_TIME = "expire_time"
CONF_ENTRY_TITLE = "Lawn Mower"
CONF_MOWER_NAME = "name"
CONF_MOWER_STATE = "mower_state"
# SENSOR
NAME_PREFIX = "imow"


class LANGUAGES(Enum):
    """Enum for languagecode mapping."""

    da = "Dansk"
    de = "Deutsch"
    en = "English"
    et = "Eesti"
    es = "Español"
    fr = "Français"
    hr = "Hrvatski"
    it = "Italiano"
    lv = "Latviešu"
    lt = "Lietuvių"
    hu = "Magyar"
    nl = "Nederlands"
    nb = "Norsk Bokmål"
    pl = "Polski"
    pt = "Português"
    ro = "Română"
    sk = "Slovenčina"
    sl = "Slovenščina"
    fi = "Suomi"
    sv = "Svenska"
    cs = "čeština"
    el = "ελληνικά"
    bg = "български"
    sr = "српски"
    ru = "русский"
