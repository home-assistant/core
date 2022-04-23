"""Constants for Scrape integration."""
from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "scrape"
DEFAULT_NAME = "Web scrape"
DEFAULT_VERIFY_SSL = True

PLATFORMS = [Platform.SENSOR]

CONF_SELECT = "select"
CONF_INDEX = "index"
