"""Constants for the deCONZ component."""
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "deconz"

CONF_BRIDGE_ID = "bridgeid"
CONF_GROUP_ID_BASE = "group_id_base"

DEFAULT_PORT = 80
DEFAULT_ALLOW_CLIP_SENSOR = False
DEFAULT_ALLOW_DECONZ_GROUPS = True

CONF_ALLOW_CLIP_SENSOR = "allow_clip_sensor"
CONF_ALLOW_DECONZ_GROUPS = "allow_deconz_groups"
CONF_MASTER_GATEWAY = "master"

SUPPORTED_PLATFORMS = [
    "binary_sensor",
    "climate",
    "cover",
    "light",
    "scene",
    "sensor",
    "switch",
]

NEW_GROUP = "groups"
NEW_LIGHT = "lights"
NEW_SCENE = "scenes"
NEW_SENSOR = "sensors"

ATTR_DARK = "dark"
ATTR_OFFSET = "offset"
ATTR_ON = "on"
ATTR_VALVE = "valve"

DAMPERS = ["Level controllable output"]
WINDOW_COVERS = ["Window covering device", "Window covering controller"]
COVER_TYPES = DAMPERS + WINDOW_COVERS

POWER_PLUGS = ["On/Off light", "On/Off plug-in unit", "Smart plug"]
SIRENS = ["Warning device"]
SWITCH_TYPES = POWER_PLUGS + SIRENS

CONF_GESTURE = "gesture"
