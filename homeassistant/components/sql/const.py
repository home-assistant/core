"""Adds constants for SQL integration."""

import re

from homeassistant.const import Platform

DOMAIN = "sql"
PLATFORMS = [Platform.SENSOR]

CONF_COLUMN_NAME = "column"
CONF_QUERY = "query"
CONF_ADDITIONAL_OPTIONS = "additional_options"
DB_URL_RE = re.compile("//.*:.*@")
