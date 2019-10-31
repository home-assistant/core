"""Constants for the Jewish Calendar integration."""
import voluptuous as vol

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
import homeassistant.helpers.config_validation as cv

CANDLE_LIGHT_DEFAULT = 18

CONF_DIASPORA = "diaspora"
CONF_LANGUAGE = "language"
CONF_CANDLE_LIGHT_MINUTES = "candle_lighting_minutes_before_sunset"
CONF_HAVDALAH_OFFSET_MINUTES = "havdalah_minutes_after_sunset"

DEFAULT_NAME = "Jewish Calendar"

DOMAIN = "jewish_calendar"

DATA_SCHEMA = {
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    vol.Optional(CONF_DIASPORA, default=False): bool,
    vol.Inclusive(CONF_LATITUDE, "coordinates"): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, "coordinates"): cv.longitude,
    vol.Optional(CONF_LANGUAGE, default="english"): vol.In(["hebrew", "english"]),
    vol.Optional(CONF_CANDLE_LIGHT_MINUTES, default=CANDLE_LIGHT_DEFAULT): int,
    # Default of 0 means use 8.5 degrees / 'three_stars' time.
    vol.Optional(CONF_HAVDALAH_OFFSET_MINUTES, default=0): int,
}
