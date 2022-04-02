"""Consts used by Tradfri."""
import logging
from typing import Final

from homeassistant.components.light import SUPPORT_TRANSITION
from homeassistant.const import Platform

_LOGGER = logging.getLogger(__name__)

ATTR_AUTO = "Auto"
ATTR_DIMMER = "dimmer"
ATTR_FILTER_LIFE_REMAINING: Final = "filter_life_remaining"
ATTR_HUE = "hue"
ATTR_SAT = "saturation"
ATTR_MAX_FAN_STEPS = 49
ATTR_MODEL = "model"
ATTR_TRADFRI_GATEWAY = "Gateway"
ATTR_TRADFRI_GATEWAY_MODEL = "E1526"
ATTR_TRADFRI_MANUFACTURER = "IKEA of Sweden"
ATTR_TRANSITION_TIME = "transition_time"
CONF_IDENTITY = "identity"
CONF_IMPORT_GROUPS = "import_groups"
CONF_GATEWAY_ID = "gateway_id"
CONF_KEY = "key"
COORDINATOR = "coordinator"
COORDINATOR_LIST = "coordinator_list"
DEVICES = "tradfri_devices"
DOMAIN = "tradfri"
FACTORY = "tradfri_factory"
KEY_API = "tradfri_api"
KEY_SECURITY_CODE = "security_code"
LISTENERS = "tradfri_listeners"
PLATFORMS = [
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]
SCAN_INTERVAL = 60  # Interval for updating the coordinator
SIGNAL_GW = "tradfri.gw_status"
SUPPORTED_LIGHT_FEATURES = SUPPORT_TRANSITION
TIMEOUT_API = 30
