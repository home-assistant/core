"""Constants for the Mealie integration."""

import logging

from awesomeversion import AwesomeVersion

DOMAIN = "mealie"

LOGGER = logging.getLogger(__package__)

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_START_DATE = "start_date"
ATTR_END_DATE = "end_date"
ATTR_RECIPE_ID = "recipe_id"
ATTR_URL = "url"
ATTR_INCLUDE_TAGS = "include_tags"

MIN_REQUIRED_MEALIE_VERSION = AwesomeVersion("v1.0.0")
