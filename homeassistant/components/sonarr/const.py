"""Constants for Sonarr."""
import logging

DOMAIN = "sonarr"

# Config Keys
CONF_BASE_PATH = "base_path"
CONF_DAYS = "days"
CONF_INCLUDED = "include_paths"
CONF_UNIT = "unit"
CONF_UPCOMING_DAYS = "upcoming_days"
CONF_WANTED_MAX_ITEMS = "wanted_max_items"

# Defaults
DEFAULT_NAME = "Sonarr"
DEFAULT_UPCOMING_DAYS = 1
DEFAULT_VERIFY_SSL = False
DEFAULT_WANTED_MAX_ITEMS = 50

LOGGER = logging.getLogger(__package__)
