"""Constants for the Entur public transport integration."""

from datetime import timedelta

DOMAIN = "entur_public_transport"

API_CLIENT_NAME = "homeassistant-{}"
ENTUR_CLIENT_NAME = "homeassistant-entur-public-transport"
GEOCODER_AUTOCOMPLETE_URL = "https://api.entur.io/geocoder/v3/autocomplete"
GEOCODER_PLACE_URL = "https://api.entur.io/geocoder/v3/place"
JOURNEY_PLANNER_URL = "https://api.entur.io/journey-planner/v3/graphql"
ENTUR_STOP_PLACE_URL = "https://entur.no/nearby-stop-place-detail?id={}"

CONF_STOP_IDS = "stop_ids"
CONF_STOP_ID = "stop_id"
CONF_QUERY = "query"
CONF_MANUAL_WHITELIST_LINES = "manual_line_whitelist"
CONF_ROUTE_LABELS = "route_labels"
CONF_STOP_PLACE_METADATA_VERSION = "stop_place_metadata_version"
CONF_STOP_PLACE_TYPES = "stop_place_types"
SUBENTRY_TYPE_STOP_PLACE = "stop_place"
CONF_EXPAND_PLATFORMS = "expand_platforms"
CONF_SHOW_ON_MAP = "show_on_map"
CONF_WHITELIST_LINES = "line_whitelist"
CONF_OMIT_NON_BOARDING = "omit_non_boarding"
CONF_NUMBER_OF_DEPARTURES = "number_of_departures"

DEFAULT_NAME = "Entur"
DEFAULT_ICON_KEY = "bus"
STOP_PLACE_METADATA_VERSION = 2

ICONS = {
    "air": "mdi:airplane",
    "bus": "mdi:bus",
    "metro": "mdi:subway",
    "rail": "mdi:train",
    "tram": "mdi:tram",
    "water": "mdi:ferry",
}

# NeTEx StopPlaceType values returned by the Entur Geocoder.  A stop place can
# have more than one type, so the UI title may contain more than one icon.
STOP_PLACE_TYPE_ICONS = {
    "airport": "✈️",
    "busStation": "🚌",
    "busPlatform": "🚏",
    "coachStation": "🚌",
    "ferryPort": "⚓",
    "ferryStop": "⛴️",
    "harbourPort": "⚓",
    "liftStation": "🚡",
    "metroStation": "🚇",
    "onstreetBus": "🚏",
    "onstreetTram": "🚋",
    "other": "🚉",
    "railStation": "🚆",
    "taxiRank": "🚕",
    "tramStation": "🚋",
    "vehicleRailInterchange": "🚗",
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
