"""Constants for the Rejseplanen integration."""

DOMAIN = "rejseplanen"

CONF_API_KEY = "api_key"
CONF_STOP_ID = "stop_id"
CONF_ROUTE = "route"
CONF_DIRECTION = "direction"
CONF_DEPARTURE_TYPE = "departure_type"
CONF_NAME = "name"

DEFAULT_NAME = "Next departure"
DEFAULT_STOP_NAME = "Unknown stop"

BUS_TYPES = ["BUS", "EXB", "TB"]
TRAIN_TYPES = ["LET", "S", "REG", "IC", "LYN", "TOG"]
METRO_TYPES = ["M"]

ATTR_STOP_ID = "stop_id"
ATTR_STOP_NAME = "stop"
ATTR_ROUTE = "route"
ATTR_TYPE = "type"
ATTR_DIRECTION = "direction"
ATTR_FINAL_STOP = "final_stop"
ATTR_DUE_IN = "due_in"
ATTR_DUE_AT = "due_at"
ATTR_SCHEDULED_AT = "scheduled_at"
ATTR_REAL_TIME_AT = "real_time_at"
ATTR_TRACK = "track"
ATTR_NEXT_UP = "next_departures"

SCAN_INTERVAL_MINUTES = 5

# User-friendly names for config flow - use string keys for cv.multi_select
DEPARTURE_TYPE_OPTIONS = {
    "ic": "InterCity trains (IC, IB)",
    "icl": "InterCity Lyn trains (ICL, ICL-X, ICL+)",
    "re": "Regional trains (Re, RA, RX)",
    "tog": "Long distance trains (EC, IR, ICE, SJ, etc.)",
    "s_tog": "S-trains (Copenhagen suburban)",
    "bus": "City buses",
    "express_bus": "Express buses",
    "night_bus": "Night & special buses",
    "flexible_bus": "Flexible transport",
    "ferry": "Ferry",
    "metro": "Metro",
    "letbane": "Light rail",
    "flight": "Flight",
}
