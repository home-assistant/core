"""Consts used by Tradfri."""
from typing import Final

from homeassistant.components.light import SUPPORT_TRANSITION
from homeassistant.const import (  # noqa: F401 pylint: disable=unused-import
    CONF_HOST,
    Platform,
)

ATTR_AUTO = "Auto"
ATTR_DIMMER = "dimmer"
ATTR_HUE = "hue"
ATTR_SAT = "saturation"
ATTR_TRADFRI_GATEWAY = "Gateway"
ATTR_TRADFRI_GATEWAY_MODEL = "E1526"
ATTR_TRADFRI_MANUFACTURER = "IKEA of Sweden"
ATTR_TRANSITION_TIME = "transition_time"
ATTR_MODEL = "model"
CONF_IDENTITY = "identity"
CONF_IMPORT_GROUPS = "import_groups"
CONF_GATEWAY_ID = "gateway_id"
CONF_KEY = "key"

DOMAIN = "tradfri"
KEY_API = "tradfri_api"
DEVICES = "tradfri_devices"
SIGNAL_GW = "tradfri.gw_status"
KEY_SECURITY_CODE = "security_code"
SUPPORTED_LIGHT_FEATURES = SUPPORT_TRANSITION
PLATFORMS = [
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]
TIMEOUT_API = 30
ATTR_MAX_FAN_STEPS = 49

SCAN_INTERVAL = 60  # Interval for updating the coordinator

COORDINATOR = "coordinator"
COORDINATOR_LIST = "coordinator_list"

ATTR_FILTER_LIFE_REMAINING: Final = "filter_life_remaining"
