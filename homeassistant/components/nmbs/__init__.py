"""The NMBS component."""

import logging

from pyrail import iRail

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_STATION_FROM, CONF_STATION_LIVE, CONF_STATION_TO, DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the NMBS component."""

    api_client = iRail()

    hass.data.setdefault(DOMAIN, {})
    station_response = await hass.async_add_executor_job(api_client.get_stations)
    if station_response == -1:
        return False
    hass.data[DOMAIN] = station_response["station"]

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NMBS from a config entry."""

    station_types = [CONF_STATION_FROM, CONF_STATION_TO, CONF_STATION_LIVE]

    for station_type in station_types:
        station = (
            next(
                (
                    s
                    for s in hass.data[DOMAIN]
                    if s["standardname"] == entry.data[station_type]
                    or s["name"] == entry.data[station_type]
                ),
                None,
            )
            if station_type in entry.data
            else None
        )
        if station is None and station_type in entry.data:
            raise ConfigEntryError(
                f"Station {entry.data[station_type]} cannot be found."
            )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
