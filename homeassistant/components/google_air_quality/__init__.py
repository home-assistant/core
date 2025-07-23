"""The Google Air Quality integration."""

import asyncio
from typing import TYPE_CHECKING

from google_air_quality_api.api import GoogleAirQualityApi
from google_air_quality_api.auth import Auth

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFERRER
from .coordinator import GoogleAirQualityConfigEntry, GoogleAirQualityUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: GoogleAirQualityConfigEntry
) -> bool:
    """Set up Google Air Quality from a config entry."""
    session = async_get_clientsession(hass)
    if TYPE_CHECKING:
        assert entry.unique_id is not None
    referrer = entry.data.get(CONF_REFERRER)
    auth = Auth(session, entry.unique_id, referrer=referrer)
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
    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GoogleAirQualityConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
