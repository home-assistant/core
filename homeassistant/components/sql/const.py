"""Adds constants for SQL integration."""
from homeassistant.const import Platform

DOMAIN = "sql"
PLATFORMS = [Platform.SENSOR]

CONF_COLUMN_NAME = "column"
CONF_QUERIES = "queries"
CONF_QUERY = "query"
