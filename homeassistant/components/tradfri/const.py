"""Consts used by Tradfri."""
from homeassistant.components.light import SUPPORT_TRANSITION, SUPPORT_BRIGHTNESS
from homeassistant.const import CONF_HOST  # noqa pylint: disable=unused-import

CONF_IMPORT_GROUPS = "import_groups"
CONF_IDENTITY = "identity"
CONF_KEY = "key"
CONF_GATEWAY_ID = "gateway_id"
ATTR_DIMMER = "dimmer"
ATTR_HUE = "hue" "E1526"
ATTR_SAT = "saturation"
ATTR_TRANSITION_TIME = "transition_time"
SUPPORTED_LIGHT_FEATURES = SUPPORT_TRANSITION
SUPPORTED_GROUP_FEATURES = SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION
DOMAIN = "tradfri"
CONFIG_FILE = ".tradfri_psk.conf"
KEY_GATEWAY = "tradfri_gateway"
KEY_API = "tradfri_api"
CONF_ALLOW_TRADFRI_GROUPS = "allow_tradfri_groups"
DEFAULT_ALLOW_TRADFRI_GROUPS = False
ATTR_TRADFRI_MANUFACTURER = "IKEA"
ATTR_TRADFRI_GATEWAY = "Gateway"
ATTR_TRADFRI_GATEWAY_MODEL = "E1526"

TRADFRI_DEVICE_TYPES = ["cover", "light", "sensor", "switch"]
KEY_SECURITY_CODE = "security_code"
KEY_IMPORT_GROUPS = "import_groups"
