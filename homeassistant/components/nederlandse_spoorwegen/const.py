"""Constants for the Nederlandse Spoorwegen integration."""

from datetime import timedelta
from zoneinfo import ZoneInfo

DOMAIN = "nederlandse_spoorwegen"
INTEGRATION_TITLE = "Nederlandse Spoorwegen"
SUBENTRY_TYPE_ROUTE = "route"
ROUTE_MODEL = "Route"
# Europe/Amsterdam timezone for Dutch rail API expectations
AMS_TZ = ZoneInfo("Europe/Amsterdam")
# Update every 2 minutes
SCAN_INTERVAL = timedelta(minutes=2)

CONF_ROUTES = "routes"
CONF_FROM = "from"
CONF_TO = "to"
CONF_VIA = "via"
CONF_TIME = "time"

# Attribute and schema keys
ATTR_ROUTE = "route"
ATTR_TRIPS = "trips"
ATTR_FIRST_TRIP = "first_trip"
ATTR_NEXT_TRIP = "next_trip"
ATTR_ROUTES = "routes"
