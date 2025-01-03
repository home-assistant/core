"""Constants for the Strip Controller integration."""

from datetime import timedelta
import logging

DOMAIN = "strip_controller"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=10)

ATTR_ON = "is_on"
ATTR_COLOR = "color"
ATTR_SECTION_ID = "section_id"

CONF_NUMBER_OF_SECTIONS = "number_of_sections"
CONF_SECTION_START = "section_start"
CONF_SECTION_END = "section_end"
CONF_SECTIONS = "sections"
