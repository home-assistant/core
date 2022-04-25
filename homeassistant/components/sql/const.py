"""Adds constants for SQL integration."""
import re

from homeassistant.const import Platform

DOMAIN = "sql"
PLATFORMS = [Platform.SENSOR]

CONF_COLUMN_NAME = "column"
CONF_QUERIES = "queries"
CONF_QUERY = "query"
DB_URL_RE = re.compile("//.*:.*@")
