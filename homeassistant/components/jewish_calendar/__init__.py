"""The jewish_calendar component."""

from __future__ import annotations

from hdate import Location
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_TIME_ZONE,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_DIASPORA,
    CONF_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_CANDLE_LIGHT,
    DEFAULT_DIASPORA,
    DEFAULT_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_LANGUAGE,
    DEFAULT_NAME,
    DOMAIN,
)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(DOMAIN),
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_DIASPORA, default=DEFAULT_DIASPORA): cv.boolean,
                vol.Inclusive(CONF_LATITUDE, "coordinates"): cv.latitude,
                vol.Inclusive(CONF_LONGITUDE, "coordinates"): cv.longitude,
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
            },
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

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        is_fixable=False,
        breaks_in_ha_version="2024.10.0",
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": DEFAULT_NAME,
        },
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up a configuration entry for Jewish calendar."""
    language = config_entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
    diaspora = config_entry.data.get(CONF_DIASPORA, DEFAULT_DIASPORA)
    candle_lighting_offset = config_entry.data.get(
        CONF_CANDLE_LIGHT_MINUTES, DEFAULT_CANDLE_LIGHT
    )
    havdalah_offset = config_entry.data.get(
        CONF_HAVDALAH_OFFSET_MINUTES, DEFAULT_HAVDALAH_OFFSET_MINUTES
    )

    location = Location(
        name=hass.config.location_name,
        diaspora=diaspora,
        latitude=config_entry.data.get(CONF_LATITUDE, hass.config.latitude),
        longitude=config_entry.data.get(CONF_LONGITUDE, hass.config.longitude),
        altitude=config_entry.data.get(CONF_ELEVATION, hass.config.elevation),
        timezone=config_entry.data.get(CONF_TIME_ZONE, hass.config.time_zone),
    )

    prefix = get_unique_prefix(
        location, language, candle_lighting_offset, havdalah_offset
    )
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        CONF_LANGUAGE: language,
        CONF_DIASPORA: diaspora,
        CONF_LOCATION: location,
        CONF_CANDLE_LIGHT_MINUTES: candle_lighting_offset,
        CONF_HAVDALAH_OFFSET_MINUTES: havdalah_offset,
        "prefix": prefix,
    }

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
