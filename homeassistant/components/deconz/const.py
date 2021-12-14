"""Constants for the deCONZ component."""
import logging

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

DOMAIN = "deconz"

CONF_BRIDGE_ID = "bridgeid"
CONF_GROUP_ID_BASE = "group_id_base"

DEFAULT_PORT = 80
DEFAULT_ALLOW_CLIP_SENSOR = False
DEFAULT_ALLOW_DECONZ_GROUPS = True
DEFAULT_ALLOW_NEW_DEVICES = True

CONF_ALLOW_CLIP_SENSOR = "allow_clip_sensor"
CONF_ALLOW_DECONZ_GROUPS = "allow_deconz_groups"
CONF_ALLOW_NEW_DEVICES = "allow_new_devices"
CONF_MASTER_GATEWAY = "master"

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SCENE,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
]

ATTR_DARK = "dark"
ATTR_LOCKED = "locked"
ATTR_OFFSET = "offset"
ATTR_ON = "on"
ATTR_VALVE = "valve"

# Switches
POWER_PLUGS = ["On/Off light", "On/Off plug-in unit", "Smart plug"]

CONF_ANGLE = "angle"
CONF_GESTURE = "gesture"
