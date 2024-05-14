"""The jewish_calendar component."""

from __future__ import annotations

from hdate import Location
import voluptuous as vol

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

DOMAIN = "jewish_calendar"
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

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


def get_unique_prefix(
    location: Location,
    language: str,
    candle_lighting_offset: int | None,
    havdalah_offset: int | None,
) -> str:
    """Create a prefix for unique ids."""
    config_properties = [
        location.latitude,
        location.longitude,
        location.timezone,
        location.altitude,
        location.diaspora,
        language,
        candle_lighting_offset,
        havdalah_offset,
    ]
    prefix = "_".join(map(str, config_properties))
    return f"{prefix}"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Jewish Calendar component."""
    if DOMAIN not in config:
        return True

    name = config[DOMAIN][CONF_NAME]
    language = config[DOMAIN][CONF_LANGUAGE]

    latitude = config[DOMAIN].get(CONF_LATITUDE, hass.config.latitude)
    longitude = config[DOMAIN].get(CONF_LONGITUDE, hass.config.longitude)
    diaspora = config[DOMAIN][CONF_DIASPORA]

    candle_lighting_offset = config[DOMAIN][CONF_CANDLE_LIGHT_MINUTES]
    havdalah_offset = config[DOMAIN][CONF_HAVDALAH_OFFSET_MINUTES]

    location = Location(
        latitude=latitude,
        longitude=longitude,
        timezone=hass.config.time_zone,
        diaspora=diaspora,
    )

    prefix = get_unique_prefix(
        location, language, candle_lighting_offset, havdalah_offset
    )
    hass.data[DOMAIN] = {
        "location": location,
        "name": name,
        "language": language,
        "candle_lighting_offset": candle_lighting_offset,
        "havdalah_offset": havdalah_offset,
        "diaspora": diaspora,
        "prefix": prefix,
    }

    for platform in PLATFORMS:
        hass.async_create_task(async_load_platform(hass, platform, DOMAIN, {}, config))

    return True
