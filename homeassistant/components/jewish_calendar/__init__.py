"""The jewish_calendar component."""
from __future__ import annotations

from hdate import Location
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_TIME_ZONE,
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_DIASPORA,
    CONF_HAVDALAH_OFFSET_MINUTES,
    CONF_LANGUAGE,
    DEFAULT_CANDLE_LIGHT,
    DEFAULT_DIASPORA,
    DEFAULT_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_LANGUAGE,
    DEFAULT_NAME,
    DOMAIN,
)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated,
            [
                {
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                    vol.Optional(CONF_DIASPORA, default=DEFAULT_DIASPORA): cv.boolean,
                    vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(
                        ["hebrew", "english"]
                    ),
                    vol.Optional(
                        CONF_CANDLE_LIGHT_MINUTES, default=DEFAULT_CANDLE_LIGHT
                    ): int,
                    # Default of 0 means use 8.5 degrees / 'three_stars' time.
                    vol.Optional(
                        CONF_HAVDALAH_OFFSET_MINUTES,
                        default=DEFAULT_HAVDALAH_OFFSET_MINUTES,
                    ): int,
                    vol.Inclusive(
                        CONF_LATITUDE,
                        "coordinates",
                        "Latitude and longitude must exist together",
                    ): cv.latitude,
                    vol.Inclusive(
                        CONF_LONGITUDE,
                        "coordinates",
                        "Latitude and longitude must exist together",
                    ): cv.longitude,
                    vol.Optional(CONF_ELEVATION): int,
                    vol.Optional(CONF_TIME_ZONE): cv.time_zone,
                }
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def get_unique_prefix(
    location: Location,
    language: str,
) -> str:
    """Create a prefix for unique ids."""
    config_properties = [
        location.latitude,
        location.longitude,
        location.diaspora,
        language,
    ]
    prefix = "_".join(map(str, config_properties))
    return f"{prefix}"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
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


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up a configuration entry for Jewish calendar."""
    name = config_entry.data[CONF_NAME]
    language = config_entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
    diaspora = config_entry.data.get(CONF_DIASPORA, DEFAULT_DIASPORA)

    if not config_entry.options:
        # If options are not defined, update entry with optional values from the
        # original configuration.
        options = {
            CONF_CANDLE_LIGHT_MINUTES: config_entry.data.get(
                CONF_CANDLE_LIGHT_MINUTES, DEFAULT_CANDLE_LIGHT
            ),
            CONF_HAVDALAH_OFFSET_MINUTES: config_entry.data.get(
                CONF_HAVDALAH_OFFSET_MINUTES, DEFAULT_HAVDALAH_OFFSET_MINUTES
            ),
        }

        hass.config_entries.async_update_entry(config_entry, options=options)

    # The current specification for config_entries of jewish_calendar allows to
    # optionally specify latitude and longitude. So we can have a config_entry with
    # CONF_LAT/LON specified, one with CONF_LOCATION or None in which case we'll
    # take the Home location.
    if config_entry.data.get(CONF_LATITUDE) or config_entry.data.get(CONF_LONGITUDE):
        latitude = config_entry.data.get(CONF_LATITUDE, hass.config.latitude)
        longitude = config_entry.data.get(CONF_LONGITUDE, hass.config.longitude)
    elif config_entry.data.get(CONF_LOCATION):
        latitude = config_entry.data[CONF_LOCATION][CONF_LATITUDE]
        longitude = config_entry.data[CONF_LOCATION][CONF_LONGITUDE]
    else:
        latitude = hass.config.latitude
        longitude = hass.config.longitude

    location = Location(
        name=hass.config.location_name,
        diaspora=diaspora,
        # If details of the location are not specified, use Hass's defaults.
        latitude=latitude,
        longitude=longitude,
        altitude=config_entry.data.get(CONF_ELEVATION, hass.config.elevation),
        timezone=config_entry.data.get(CONF_TIME_ZONE, hass.config.time_zone),
    )

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "name": name,
        "language": language,
        "diaspora": diaspora,
        "location": location,
        "candle_lighting_offset": config_entry.options.get(
            CONF_CANDLE_LIGHT_MINUTES, DEFAULT_CANDLE_LIGHT
        ),
        "havdalah_offset": config_entry.options.get(
            CONF_HAVDALAH_OFFSET_MINUTES, DEFAULT_HAVDALAH_OFFSET_MINUTES
        ),
        "prefix": get_unique_prefix(
            location,
            language,
        ),
    }

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
