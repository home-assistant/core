"""The buienradar integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_TIMEFRAME, DEFAULT_TIMEFRAME
from .util import BrData

PLATFORMS = [Platform.CAMERA, Platform.SENSOR, Platform.WEATHER]

type BuienRadarConfigEntry = ConfigEntry[BrData]


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: BuienRadarConfigEntry) -> bool:
    """Set up buienradar from a config entry."""
    config = entry.data
    options = entry.options

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    coordinates = {CONF_LATITUDE: float(latitude), CONF_LONGITUDE: float(longitude)}

    timeframe = options.get(
        CONF_TIMEFRAME, config.get(CONF_TIMEFRAME, DEFAULT_TIMEFRAME)
    )

    # create weather data:
    _LOGGER.debug(
        "Initializing buienradar data coordinate %s, timeframe %s",
        coordinates,
        timeframe,
    )
    data = BrData(hass, coordinates, timeframe, [])
    entry.runtime_data = data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    await data.async_update()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BuienRadarConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        if (data := entry.runtime_data) and (unsub := data.unsub_schedule_update):
            unsub()

    return unload_ok


async def async_update_options(
    hass: HomeAssistant, config_entry: BuienRadarConfigEntry
) -> None:
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)
