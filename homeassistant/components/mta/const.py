"""Constants for the MTA New York City Transit integration."""

from datetime import timedelta

DOMAIN = "mta"

CONF_LINE = "line"
CONF_STOP_ID = "stop_id"
CONF_STOP_NAME = "stop_name"
CONF_ROUTE = "route"

SUBENTRY_TYPE_SUBWAY = "subway"
SUBENTRY_TYPE_BUS = "bus"

UPDATE_INTERVAL = timedelta(seconds=30)
