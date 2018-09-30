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

ATTR_DARK = 'dark'
ATTR_ON = 'on'

COVER_TYPES = ["Level controllable output"]

POWER_PLUGS = ["On/Off plug-in unit", "Smart plug"]
SIRENS = ["Warning device"]
SWITCH_TYPES = POWER_PLUGS + SIRENS
