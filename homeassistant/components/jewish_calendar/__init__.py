"""The jewish_calendar component."""
import logging

import hdate
import voluptuous as vol

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

_LOGGER = logging.getLogger(__name__)

DOMAIN = "jewish_calendar"

SENSOR_TYPES = {
    "binary": {
        "issur_melacha_in_effect": ["Issur Melacha in Effect", "mdi:power-plug-off"]
    },
    "data": {
        "date": ["Date", "mdi:judaism"],
        "weekly_portion": ["Parshat Hashavua", "mdi:book-open-variant"],
        "holiday": ["Holiday", "mdi:calendar-star"],
        "omer_count": ["Day of the Omer", "mdi:counter"],
        "daf_yomi": ["Daf Yomi", "mdi:book-open-variant"],
    },
    "time": {
        "first_light": ["Alot Hashachar", "mdi:weather-sunset-up"],
        "talit": ["Talit and Tefillin", "mdi:calendar-clock"],
        "gra_end_shma": ['Latest time for Shma Gr"a', "mdi:calendar-clock"],
        "mga_end_shma": ['Latest time for Shma MG"A', "mdi:calendar-clock"],
        "gra_end_tfila": ['Latest time for Tefilla MG"A', "mdi:calendar-clock"],
        "mga_end_tfila": ['Latest time for Tefilla Gr"a', "mdi:calendar-clock"],
        "big_mincha": ["Mincha Gedola", "mdi:calendar-clock"],
        "small_mincha": ["Mincha Ketana", "mdi:calendar-clock"],
        "plag_mincha": ["Plag Hamincha", "mdi:weather-sunset-down"],
        "sunset": ["Shkia", "mdi:weather-sunset"],
        "first_stars": ["T'set Hakochavim", "mdi:weather-night"],
        "upcoming_shabbat_candle_lighting": [
            "Upcoming Shabbat Candle Lighting",
            "mdi:candle",
        ],
        "upcoming_shabbat_havdalah": ["Upcoming Shabbat Havdalah", "mdi:weather-night"],
        "upcoming_candle_lighting": ["Upcoming Candle Lighting", "mdi:candle"],
        "upcoming_havdalah": ["Upcoming Havdalah", "mdi:weather-night"],
    },
}

CONF_DIASPORA = "diaspora"
CONF_LANGUAGE = "language"
CONF_CANDLE_LIGHT_MINUTES = "candle_lighting_minutes_before_sunset"
CONF_HAVDALAH_OFFSET_MINUTES = "havdalah_minutes_after_sunset"

CANDLE_LIGHT_DEFAULT = 18

DEFAULT_NAME = "Jewish Calendar"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_DIASPORA, default=False): cv.boolean,
                vol.Inclusive(CONF_LATITUDE, "coordinates"): cv.latitude,
                vol.Inclusive(CONF_LONGITUDE, "coordinates"): cv.longitude,
                vol.Optional(CONF_LANGUAGE, default="english"): vol.In(
                    ["hebrew", "english"]
                ),
                vol.Optional(
                    CONF_CANDLE_LIGHT_MINUTES, default=CANDLE_LIGHT_DEFAULT
                ): int,
                # Default of 0 means use 8.5 degrees / 'three_stars' time.
                vol.Optional(CONF_HAVDALAH_OFFSET_MINUTES, default=0): int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Jewish Calendar component."""
    name = config[DOMAIN][CONF_NAME]
    language = config[DOMAIN][CONF_LANGUAGE]

    latitude = config[DOMAIN].get(CONF_LATITUDE, hass.config.latitude)
    longitude = config[DOMAIN].get(CONF_LONGITUDE, hass.config.longitude)
    diaspora = config[DOMAIN][CONF_DIASPORA]

    candle_lighting_offset = config[DOMAIN][CONF_CANDLE_LIGHT_MINUTES]
    havdalah_offset = config[DOMAIN][CONF_HAVDALAH_OFFSET_MINUTES]

    location = hdate.Location(
        latitude=latitude,
        longitude=longitude,
        timezone=hass.config.time_zone,
        diaspora=diaspora,
    )

    hass.data[DOMAIN] = {
        "location": location,
        "name": name,
        "language": language,
        "candle_lighting_offset": candle_lighting_offset,
        "havdalah_offset": havdalah_offset,
        "diaspora": diaspora,
    }

    hass.async_create_task(async_load_platform(hass, "sensor", DOMAIN, {}, config))

    hass.async_create_task(
        async_load_platform(hass, "binary_sensor", DOMAIN, {}, config)
    )

    return True
