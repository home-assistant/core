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
DEFAULT_ALLOW_HUE_GROUPS = True

CONF_INCLUDE_HUE_SENSORS = "add_hue_sensors"
DEFAULT_INCLUDE_HUE_SENSORS = True

CONF_INCLUDE_HUE_REMOTES = "add_hue_remotes"
DEFAULT_INCLUDE_HUE_REMOTES = False
