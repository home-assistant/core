"""Constants for the Entur public transport integration."""

from datetime import timedelta

DOMAIN = "entur_public_transport"

API_CLIENT_NAME = "homeassistant-{}"
ENTUR_CLIENT_NAME = "homeassistant-entur-public-transport"
GEOCODER_AUTOCOMPLETE_URL = "https://api.entur.io/geocoder/v3/autocomplete"
JOURNEY_PLANNER_URL = "https://api.entur.io/journey-planner/v3/graphql"
ENTUR_STOP_PLACE_URL = "https://entur.no/nearby-stop-place-detail?id={}"

CONF_STOP_IDS = "stop_ids"
CONF_STOP_ID = "stop_id"
CONF_QUERY = "query"
CONF_MANUAL_WHITELIST_LINES = "manual_line_whitelist"
SUBENTRY_TYPE_STOP_PLACE = "stop_place"
CONF_EXPAND_PLATFORMS = "expand_platforms"
CONF_SHOW_ON_MAP = "show_on_map"
CONF_WHITELIST_LINES = "line_whitelist"
CONF_OMIT_NON_BOARDING = "omit_non_boarding"
CONF_NUMBER_OF_DEPARTURES = "number_of_departures"

DEFAULT_NAME = "Entur"
DEFAULT_ICON_KEY = "bus"

ICONS = {
    "air": "mdi:airplane",
    "bus": "mdi:bus",
    "metro": "mdi:subway",
    "rail": "mdi:train",
    "tram": "mdi:tram",
    "water": "mdi:ferry",
}

SCAN_INTERVAL = timedelta(seconds=45)

ATTR_STOP_ID = "stop_id"

ATTR_ROUTE = "route"
ATTR_ROUTE_ID = "route_id"
ATTR_EXPECTED_AT = "due_at"
ATTR_DELAY = "delay"
ATTR_REALTIME = "real_time"

ATTR_NEXT_UP_IN = "next_due_in"
ATTR_NEXT_UP_ROUTE = "next_route"
ATTR_NEXT_UP_ROUTE_ID = "next_route_id"
ATTR_NEXT_UP_AT = "next_due_at"
ATTR_NEXT_UP_DELAY = "next_delay"
ATTR_NEXT_UP_REALTIME = "next_real_time"

ATTR_TRANSPORT_MODE = "transport_mode"
