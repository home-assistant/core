"""Constants for the Nederlandse Spoorwegen integration."""

DOMAIN = "nederlandse_spoorwegen"

CONF_ROUTES = "routes"
CONF_FROM = "from"
CONF_TO = "to"
CONF_VIA = "via"
CONF_TIME = "time"
CONF_NAME = "name"
CONF_ACTION = "action"
CONF_ROUTE_IDX = "route_idx"

# Attribute and schema keys
ATTR_ATTRIBUTION = "Data provided by NS"
ATTR_ICON = "mdi:train"
ATTR_ROUTE = "route"
ATTR_TRIPS = "trips"
ATTR_FIRST_TRIP = "first_trip"
ATTR_NEXT_TRIP = "next_trip"
ATTR_STATIONS = "stations"
ATTR_ROUTES = "routes"
ATTR_ROUTE_KEY = "route_key"
ATTR_SERVICE = "service"

# Service schemas
SERVICE_ADD_ROUTE = "add_route"
SERVICE_REMOVE_ROUTE = "remove_route"

MIN_TIME_BETWEEN_UPDATES_SECONDS = 120

PARALLEL_UPDATES = 2

STATION_LIST_URL = (
    "https://nl.wikipedia.org/wiki/Lijst_van_spoorwegstations_in_Nederland"
)
