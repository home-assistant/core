"""Constants for the MTA New York City Transit integration."""

from datetime import timedelta

DOMAIN = "mta"

CONF_LINE = "line"
CONF_STOP_ID = "stop_id"
CONF_STOP_NAME = "stop_name"

UPDATE_INTERVAL = timedelta(seconds=30)
