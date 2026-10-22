"""Constants for Google Travel Time."""

DOMAIN = "google_travel_time"

ATTRIBUTION = "Powered by Google"

CONF_DESTINATION = "destination"
CONF_ORIGIN = "origin"
CONF_AVOID = "avoid"
CONF_UNITS = "units"
CONF_ARRIVAL_TIME = "arrival_time"
CONF_DEPARTURE_TIME = "departure_time"
CONF_TRAFFIC_MODEL = "traffic_model"
CONF_TRANSIT_MODE = "transit_mode"
CONF_TRANSIT_ROUTING_PREFERENCE = "transit_routing_preference"
CONF_TIME_TYPE = "time_type"
CONF_TIME = "time"
CONF_REFERRER = "referrer"
SECTION_API_KEY_OPTIONS = "api_key_options"

ARRIVAL_TIME = "Arrival Time"
DEPARTURE_TIME = "Departure Time"
TIME_TYPES = [ARRIVAL_TIME, DEPARTURE_TIME]

DEFAULT_NAME = "Google Travel Time"

ALL_LANGUAGES = [
    "ar",
    "bg",
    "bn",
    "ca",
    "cs",
    "da",
    "de",
    "el",
    "en",
    "es",
    "eu",
    "fa",
    "fi",
    "fr",
    "gl",
    "gu",
    "hi",
    "hr",
    "hu",
    "id",
    "it",
    "iw",
    "ja",
    "kn",
    "ko",
    "lt",
    "lv",
    "ml",
    "mr",
    "nl",
    "no",
    "pl",
    "pt",
    "pt-BR",
    "pt-PT",
    "ro",
    "ru",
    "sk",
    "sl",
    "sr",
    "sv",
    "ta",
    "te",  # codespell:ignore te
    "th",
    "tl",
    "tr",
    "uk",
    "vi",
    "zh-CN",
    "zh-TW",
]

AVOID_OPTIONS = ["tolls", "highways", "ferries", "indoor"]
TRANSIT_PREFS = ["less_walking", "fewer_transfers"]
TRANSIT_PREFS_TO_API = {
    "less_walking": "LESS_WALKING",
    "fewer_transfers": "FEWER_TRANSFERS",
}
TRANSPORT_TYPES = ["bus", "subway", "train", "tram", "rail"]
TRANSPORT_TYPES_TO_API = {
    "bus": "BUS",
    "subway": "SUBWAY",
    "train": "TRAIN",
    "tram": "LIGHT_RAIL",
    "rail": "RAIL",
}
TRAVEL_MODES = ["driving", "walking", "bicycling", "transit"]
TRAVEL_MODES_WITHOUT_TRANSIT = ["driving", "walking", "bicycling"]
TRAVEL_MODES_TO_API = {
    "driving": "DRIVE",
    "walking": "WALK",
    "bicycling": "BICYCLE",
    "transit": "TRANSIT",
}
TRAFFIC_MODELS = ["best_guess", "pessimistic", "optimistic"]
TRAFFIC_MODELS_TO_API = {
    "best_guess": "BEST_GUESS",
    "pessimistic": "PESSIMISTIC",
    "optimistic": "OPTIMISTIC",
}

UNITS_METRIC = "metric"
UNITS_IMPERIAL = "imperial"
UNITS = [UNITS_METRIC, UNITS_IMPERIAL]
UNITS_TO_API = {
    UNITS_METRIC: "METRIC",
    UNITS_IMPERIAL: "IMPERIAL",
}
