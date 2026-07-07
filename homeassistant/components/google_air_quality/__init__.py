"""The Google Air Quality integration."""

import asyncio

from google_air_quality_api.api import GoogleAirQualityApi
from google_air_quality_api.auth import Auth

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import CONF_REFERRER, DOMAIN
from .coordinator import (
    GoogleAirQualityConfigEntry,
    GoogleAirQualityRuntimeData,
    GoogleAirQualityUpdateCoordinator,
)
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Google Air Quality integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: GoogleAirQualityConfigEntry
) -> bool:
    """Set up Google Air Quality from a config entry."""
    session = async_get_clientsession(hass)
    api_key = entry.data[CONF_API_KEY]
    referrer = entry.data.get(CONF_REFERRER)
    auth = Auth(session, api_key, referrer=referrer)
    client = GoogleAirQualityApi(auth)
    coordinators: dict[str, GoogleAirQualityUpdateCoordinator] = {}
    for subentry_id in entry.subentries:
        coordinators[subentry_id] = GoogleAirQualityUpdateCoordinator(
            hass, entry, subentry_id, client
        )
    await asyncio.gather(
        *(
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators.values()
        )
    )
    entry.runtime_data = GoogleAirQualityRuntimeData(
        api=client,
        subentries_runtime_data=coordinators,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GoogleAirQualityConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(
    hass: HomeAssistant, entry: GoogleAirQualityConfigEntry
) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
