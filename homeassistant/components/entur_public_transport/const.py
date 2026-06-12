"""Constants for the Entur public transport integration."""

from datetime import timedelta

DOMAIN = "entur_public_transport"

API_CLIENT_NAME = "homeassistant-{}"

CONF_STOP_IDS = "stop_ids"
CONF_EXPAND_PLATFORMS = "expand_platforms"
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
