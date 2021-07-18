"""Constants for the STIHL iMow integration."""
import logging
from typing import Final

API_UPDATE_INTERVALL_SECONDS = 30
API_DEFAULT_LANGUAGE = "English"
API_UPDATE_TIMEOUT = 10

ATTR_COORDINATOR = "coordinator"
ATTR_SWITCH = "switch"
ATTR_ID = "id"
ATTR_SHORT = "short"
ATTR_LONG = "long"
ATTR_IMOW = "imow"
ATTR_PICTURE = "picture"
ATTR_UOM = "uom"
ATTR_TYPE = "type"
ATTR_ICON = "icon"
ATTR_NAME = "name"
ATTR_MANUFACTURER = "manufacturer"
ATTR_MODEL = "model"
ATTR_SW_VERSION = "sw_version"

DOMAIN = "stihl_imow"
CONF_USER_INPUT = "user_input"
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

# Config Flow
CONF_ATTR_EMAIL = "email"
CONF_ATTR_PASSWORD = "password"
CONF_ATTR_LANGUAGE = "language"
CONF_ATTR_POLLING_INTERVALL = "polling_interval"

# SENSOR
NAME_PREFIX = "imow"
LOGGER: Final[logging.Logger] = logging.getLogger(__package__)
