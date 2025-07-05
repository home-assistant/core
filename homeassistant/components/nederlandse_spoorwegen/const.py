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

MIN_TIME_BETWEEN_UPDATES_SECONDS = 120

ATTR_ATTRIBUTION = "Data provided by NS"
ATTR_ICON = "mdi:train"

PARALLEL_UPDATES = 2

STATION_LIST_URL = (
    "https://nl.wikipedia.org/wiki/Lijst_van_spoorwegstations_in_Nederland"
)
