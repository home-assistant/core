"""Adds constants for SQL integration."""

import re

from homeassistant.const import Platform

DOMAIN = "sql"
PLATFORMS = [Platform.SENSOR]

CONF_COLUMN_NAME = "column"
CONF_QUERY = "query"
CONF_ADVANCED_OPTIONS = "advanced_options"
DB_URL_RE = re.compile("//.*:.*@")
