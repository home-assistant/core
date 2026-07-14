"""Constants for the Tewke integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "tewke"
DISPATCHER_ADD_SCENES = "tewke_add_scenes"

CONF_DEFAULT_SCENE_FAN_DIMMING = "default_scene_fan_dimming"
CONF_DISABLED_SCENES = "disabled_scenes"
DEFAULT_SCENE_FAN_DIMMING = 50
