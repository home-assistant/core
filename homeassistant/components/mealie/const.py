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
ATTR_ENTRY_TYPE = "entry_type"
ATTR_NOTE_TITLE = "note_title"
ATTR_NOTE_TEXT = "note_text"

MIN_REQUIRED_MEALIE_VERSION = AwesomeVersion("v1.0.0")
