"""Constants for the Mobility Database integration."""

from datetime import timedelta

DOMAIN = "mobility_database"

CONF_REFRESH_TOKEN = "refresh_token"
CONF_FEED_ID = "feed_id"
CONF_SEARCH_QUERY = "search_query"

SUBENTRY_TYPE_STOP = "stop"
CONF_STOP_ID = "stop_id"
CONF_STOP_NAME = "stop_name"
CONF_ROUTE_IDS = "route_ids"
CONF_HEADSIGNS = "headsigns"

STATIC_REFRESH_INTERVAL = timedelta(hours=24)
ARRIVALS_INTERVAL_REALTIME = timedelta(seconds=60)
ARRIVALS_INTERVAL_SCHEDULE = timedelta(minutes=5)

ISSUE_STOP_MISSING = "stop_missing"
