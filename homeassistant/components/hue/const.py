"""Constants for the Hue component."""
import logging

LOGGER = logging.getLogger(__package__)
DOMAIN = "hue"

# How long to wait to actually do the refresh after requesting it.
# We wait some time so if we control multiple lights, we batch requests.
REQUEST_REFRESH_DELAY = 0.3

CONF_ALLOW_UNREACHABLE = "allow_unreachable"
DEFAULT_ALLOW_UNREACHABLE = False

CONF_ALLOW_HUE_GROUPS = "allow_hue_groups"
DEFAULT_ALLOW_HUE_GROUPS = False

GROUP_TYPE_LIGHT_GROUP = "LightGroup"
GROUP_TYPE_ROOM = "Room"
GROUP_TYPE_LUMINAIRE = "Luminaire"
GROUP_TYPE_LIGHT_SOURCE = "LightSource"

ATTR_GROUP_NAME = "group_name"
ATTR_SCENE_NAME = "scene_name"
ATTR_TRANSITION = "transition"
