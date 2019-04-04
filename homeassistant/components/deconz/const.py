"""Constants for the deCONZ component."""
import logging

_LOGGER = logging.getLogger('.')

DOMAIN = 'deconz'

DEFAULT_PORT = 80
DEFAULT_ALLOW_CLIP_SENSOR = False
DEFAULT_ALLOW_DECONZ_GROUPS = False

CONF_ALLOW_CLIP_SENSOR = 'allow_clip_sensor'
CONF_ALLOW_DECONZ_GROUPS = 'allow_deconz_groups'
CONF_BRIDGEID = 'bridgeid'

SUPPORTED_PLATFORMS = ['binary_sensor', 'climate', 'cover',
                       'light', 'scene', 'sensor', 'switch']

DECONZ_REACHABLE = 'deconz_reachable'

NEW_GROUP = 'deconz_new_group'
NEW_LIGHT = 'deconz_new_light'
NEW_SCENE = 'deconz_new_scene'
NEW_SENSOR = 'deconz_new_sensor'

NEW_DEVICE = {
    'group': NEW_GROUP,
    'light': NEW_LIGHT,
    'scene': NEW_SCENE,
    'sensor': NEW_SENSOR
}

ATTR_DARK = 'dark'
ATTR_OFFSET = 'offset'
ATTR_ON = 'on'
ATTR_VALVE = 'valve'

DAMPERS = ["Level controllable output"]
WINDOW_COVERS = ["Window covering device"]
COVER_TYPES = DAMPERS + WINDOW_COVERS

POWER_PLUGS = ["On/Off plug-in unit", "Smart plug"]
SIRENS = ["Warning device"]
SWITCH_TYPES = POWER_PLUGS + SIRENS
