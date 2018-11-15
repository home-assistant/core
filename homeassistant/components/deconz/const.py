"""Constants for the deCONZ component."""
import logging

_LOGGER = logging.getLogger('homeassistant.components.deconz')

DOMAIN = 'deconz'
CONFIG_FILE = 'deconz.conf'
DATA_DECONZ_EVENT = 'deconz_events'
DATA_DECONZ_ID = 'deconz_entities'
DATA_DECONZ_UNSUB = 'deconz_dispatchers'
DECONZ_DOMAIN = 'deconz'

CONF_ALLOW_CLIP_SENSOR = 'allow_clip_sensor'
CONF_ALLOW_DECONZ_GROUPS = 'allow_deconz_groups'

SUPPORTED_PLATFORMS = ['binary_sensor', 'cover',
                       'light', 'scene', 'sensor', 'switch']

ATTR_DARK = 'dark'
ATTR_ON = 'on'

DAMPERS = ["Level controllable output"]
WINDOW_COVERS = ["Window covering device"]
COVER_TYPES = DAMPERS + WINDOW_COVERS

POWER_PLUGS = ["On/Off plug-in unit", "Smart plug"]
SIRENS = ["Warning device"]
SWITCH_TYPES = POWER_PLUGS + SIRENS
