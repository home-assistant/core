"""Constants for Scrape integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "scrape"
DEFAULT_NAME = "Web scrape"
DEFAULT_VERIFY_SSL = True
DEFAULT_SCAN_INTERVAL = timedelta(minutes=10)

PLATFORMS = [Platform.SENSOR]

CONF_SELECT = "select"
CONF_INDEX = "index"
