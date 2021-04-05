"""Constants for Google Travel Time."""
from homeassistant.const import CONF_UNIT_SYSTEM_IMPERIAL, CONF_UNIT_SYSTEM_METRIC

DOMAIN = "google_travel_time"

ATTRIBUTION = "Powered by Google"

CONF_DESTINATION = "destination"
CONF_OPTIONS = "options"
CONF_ORIGIN = "origin"
CONF_TRAVEL_MODE = "travel_mode"
CONF_LANGUAGE = "language"
CONF_AVOID = "avoid"
CONF_UNITS = "units"
CONF_ARRIVAL_TIME = "arrival_time"
CONF_DEPARTURE_TIME = "departure_time"
CONF_TRAFFIC_MODEL = "traffic_model"
CONF_TRANSIT_MODE = "transit_mode"
CONF_TRANSIT_ROUTING_PREFERENCE = "transit_routing_preference"
CONF_TIME_TYPE = "time_type"
CONF_TIME = "time"

ARRIVAL_TIME = "Arrival Time"
DEPARTURE_TIME = "Departure Time"
TIME_TYPES = [ARRIVAL_TIME, DEPARTURE_TIME]

DEFAULT_NAME = "Google Travel Time"

TRACKABLE_DOMAINS = ["device_tracker", "sensor", "zone", "person"]

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
    "te",
    "th",
    "tl",
    "tr",
    "uk",
    "vi",
    "zh-CN",
    "zh-TW",
]

AVOID = ["tolls", "highways", "ferries", "indoor"]
TRANSIT_PREFS = ["less_walking", "fewer_transfers"]
TRANSPORT_TYPE = ["bus", "subway", "train", "tram", "rail"]
TRAVEL_MODE = ["driving", "walking", "bicycling", "transit"]
TRAVEL_MODEL = ["best_guess", "pessimistic", "optimistic"]
UNITS = [CONF_UNIT_SYSTEM_METRIC, CONF_UNIT_SYSTEM_IMPERIAL]
