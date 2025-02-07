"""The jewish_calendar component."""

from __future__ import annotations

from functools import partial

from hdate import Location

from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_TIME_ZONE,
    Platform,
)
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_DIASPORA,
    CONF_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_CANDLE_LIGHT,
    DEFAULT_DIASPORA,
    DEFAULT_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_LANGUAGE,
)
from .entity import JewishCalendarConfigEntry, JewishCalendarData

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: JewishCalendarConfigEntry
) -> bool:
    """Set up a configuration entry for Jewish calendar."""
    language = config_entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
    diaspora = config_entry.data.get(CONF_DIASPORA, DEFAULT_DIASPORA)
    candle_lighting_offset = config_entry.options.get(
        CONF_CANDLE_LIGHT_MINUTES, DEFAULT_CANDLE_LIGHT
    )
    havdalah_offset = config_entry.options.get(
        CONF_HAVDALAH_OFFSET_MINUTES, DEFAULT_HAVDALAH_OFFSET_MINUTES
    )

    location = await hass.async_add_executor_job(
        partial(
            Location,
            name=hass.config.location_name,
            diaspora=diaspora,
            latitude=config_entry.data.get(CONF_LATITUDE, hass.config.latitude),
            longitude=config_entry.data.get(CONF_LONGITUDE, hass.config.longitude),
            altitude=config_entry.data.get(CONF_ELEVATION, hass.config.elevation),
            timezone=config_entry.data.get(CONF_TIME_ZONE, hass.config.time_zone),
        )
    )

    config_entry.runtime_data = JewishCalendarData(
        language,
        diaspora,
        location,
        candle_lighting_offset,
        havdalah_offset,
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    async def update_listener(
        hass: HomeAssistant, config_entry: JewishCalendarConfigEntry
    ) -> None:
        # Trigger update of states for all platforms
        await hass.config_entries.async_reload(config_entry.entry_id)

    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))
    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: JewishCalendarConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
