"""Constants for the MobilityData integration."""

from datetime import timedelta

DOMAIN = "mobilitydata"

CONF_REFRESH_TOKEN = "refresh_token"
CONF_FEED_ID = "feed_id"
CONF_SEARCH_QUERY = "search_query"

SUBENTRY_TYPE_STOP = "stop"
CONF_STATION_ID = "station_id"
CONF_STOP_IDS = "stop_ids"
CONF_STOP_NAME = "stop_name"
CONF_ROUTE_IDS = "route_ids"
# Route -> destination pairs, each a [route_id, headsign] list; a null
# headsign means every departure of that route. Empty means "every departure
# of the routes in CONF_ROUTE_IDS" (or of the whole station).
CONF_ROUTE_DESTINATIONS = "route_destinations"

STATIC_REFRESH_INTERVAL = timedelta(hours=24)
# Until the first static refresh lands there is no index to query, so every
# entity stays unavailable; retry on a short interval rather than making a
# transient startup outage last a whole day.
STATIC_RETRY_INTERVAL = timedelta(minutes=5)
ARRIVALS_INTERVAL_REALTIME = timedelta(seconds=60)
ARRIVALS_INTERVAL_SCHEDULE = timedelta(minutes=5)

# One sensor per upcoming departure, and the per-board query limit that
# feeds them: asking the library for more rows than this would discard them.
DEPARTURE_SENSOR_COUNT = 3

ISSUE_STOP_MISSING = "stop_missing"
