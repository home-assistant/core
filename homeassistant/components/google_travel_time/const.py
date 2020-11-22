"""Constants for Google Travel Time."""
import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
)
import homeassistant.helpers.config_validation as cv

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

GOOGLE_SCHEMA = {
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_DESTINATION): cv.string,
    vol.Required(CONF_ORIGIN): cv.string,
    vol.Optional(CONF_NAME): cv.string,
}

GOOGLE_IMPORT_SCHEMA = {
    **GOOGLE_SCHEMA,
    vol.Optional(CONF_TRAVEL_MODE): vol.In(TRAVEL_MODE),
}

GOOGLE_OPTIONS_SCHEMA = {
    vol.Optional(CONF_MODE, default="driving"): vol.In(TRAVEL_MODE),
    vol.Optional(CONF_LANGUAGE): vol.In(ALL_LANGUAGES),
    vol.Optional(CONF_AVOID): vol.In(AVOID),
    vol.Optional(CONF_UNITS): vol.In(UNITS),
    vol.Exclusive(CONF_ARRIVAL_TIME, "time"): cv.string,
    vol.Exclusive(CONF_DEPARTURE_TIME, "time"): cv.string,
    vol.Optional(CONF_TRAFFIC_MODEL): vol.In(TRAVEL_MODEL),
    vol.Optional(CONF_TRANSIT_MODE): vol.In(TRANSPORT_TYPE),
    vol.Optional(CONF_TRANSIT_ROUTING_PREFERENCE): vol.In(TRANSIT_PREFS),
}
