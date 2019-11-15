"""The jewish_calendar component."""
import asyncio
import logging

import voluptuous as vol
import hdate

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_LANGUAGE,
    CONF_DIASPORA,
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_NAME,
    DEFAULT_LANGUAGE,
    DEFAULT_DIASPORA,
    DEFAULT_CANDLE_LIGHT,
    DEFAULT_HAVDALAH_OFFSET_MINUTES,
    DOMAIN,
)


_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "binary": {
        "issur_melacha_in_effect": ["Issur Melacha in Effect", "mdi:power-plug-off"]
    },
    "data": {
        "date": ["Date", "mdi:judaism"],
        "weekly_portion": ["Parshat Hashavua", "mdi:book-open-variant"],
        "holiday": ["Holiday", "mdi:calendar-star"],
        "omer_count": ["Day of the Omer", "mdi:counter"],
    },
    "time": {
        "first_light": ["Alot Hashachar", "mdi:weather-sunset-up"],
        "gra_end_shma": ['Latest time for Shm"a GR"A', "mdi:calendar-clock"],
        "mga_end_shma": ['Latest time for Shm"a MG"A', "mdi:calendar-clock"],
        "plag_mincha": ["Plag Hamincha", "mdi:weather-sunset-down"],
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

JEWISH_CALENDAR_SCHEMA = {
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DIASPORA, default=DEFAULT_DIASPORA): cv.boolean,
    vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(
        ["hebrew", "english"]
    ),
    vol.Optional(CONF_CANDLE_LIGHT_MINUTES, default=DEFAULT_CANDLE_LIGHT): int,
    # Default of 0 means use 8.5 degrees / 'three_stars' time.
    vol.Optional(
        CONF_HAVDALAH_OFFSET_MINUTES, default=DEFAULT_HAVDALAH_OFFSET_MINUTES
    ): int,
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
}

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [JEWISH_CALENDAR_SCHEMA])}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass, config):
    """Set up the Jewish Calendar component."""
    if DOMAIN not in config:
        return True

    for entry in config[DOMAIN]:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
            )
        )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up a config entry for Jewish calendar."""
    name = config_entry.data[CONF_NAME]
    language = config_entry.data[CONF_LANGUAGE]
    diaspora = config_entry.data[CONF_DIASPORA]

    latitude = config_entry.data.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config_entry.data.get(CONF_LONGITUDE, hass.config.longitude)
    candle_lighting_offset = config_entry.data.get(
        CONF_CANDLE_LIGHT_MINUTES, DEFAULT_CANDLE_LIGHT
    )
    havdalah_offset = config_entry.data.get(
        CONF_HAVDALAH_OFFSET_MINUTES, DEFAULT_HAVDALAH_OFFSET_MINUTES
    )

    if not config_entry.options:
        options = {
            CONF_LATITUDE: latitude,
            CONF_LONGITUDE: longitude,
            CONF_CANDLE_LIGHT_MINUTES: candle_lighting_offset,
            CONF_HAVDALAH_OFFSET_MINUTES: havdalah_offset,
        }

        hass.config_entries.async_update_entry(config_entry, options=options)

    location = hdate.Location(
        latitude=latitude,
        longitude=longitude,
        timezone=hass.config.time_zone,
        diaspora=diaspora,
    )

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "location": location,
        "name": name,
        "language": language,
        "candle_lighting_offset": candle_lighting_offset,
        "havdalah_offset": havdalah_offset,
        "diaspora": diaspora,
    }

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "binary_sensor")
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await asyncio.gather(
        hass.config_entries.async_forward_entry_unload(config_entry, "sensor"),
        hass.config_entries.async_forward_entry_unload(config_entry, "binary_sensor"),
    )
    hass.data[DOMAIN].pop(config_entry.entry_id)
    return True
