"""The jewish_calendar component."""
from copy import deepcopy
import asyncio
import logging

import voluptuous as vol
import hdate

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

from .const import (
    CONF_LANGUAGE,
    CONF_DIASPORA,
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_HAVDALAH_OFFSET_MINUTES,
    DOMAIN,
    DATA_SCHEMA,
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

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema(DATA_SCHEMA)}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Jewish Calendar component."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=deepcopy(conf)
        )
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry for Jewish calendar."""
    name = entry.data[CONF_NAME]
    language = entry.data[CONF_LANGUAGE]

    latitude = entry.data.get(CONF_LATITUDE, hass.config.latitude)
    longitude = entry.data.get(CONF_LONGITUDE, hass.config.longitude)
    diaspora = entry.data[CONF_DIASPORA]

    candle_lighting_offset = entry.data[CONF_CANDLE_LIGHT_MINUTES]
    havdalah_offset = entry.data[CONF_HAVDALAH_OFFSET_MINUTES]

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

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "binary_sensor")
    )

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    await asyncio.gather(
        hass.config_entries.async_forward_entry_unload(entry, "sensor"),
        hass.config_entries.async_forward_entry_unload(entry, "binary_sensor"),
    )
    return True
