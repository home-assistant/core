"""The Google Air Quality integration."""

from __future__ import annotations

import asyncio

from aiohttp import ClientError, ClientResponseError
from google_air_quality_api.api import GoogleAirQualityApi

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import api
from .coordinator import GoogleAirQualityConfigEntry, GoogleAirQualityUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: GoogleAirQualityConfigEntry
) -> bool:
    """Set up Google Air Quality from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    web_session = async_get_clientsession(hass)
    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    auth = api.AsyncConfigEntryAuth(web_session, oauth_session)

    try:
        await auth.async_get_access_token()
    except (ClientResponseError, ClientError) as err:
        raise ConfigEntryNotReady from err

    api_client = GoogleAirQualityApi(auth)

    coordinators: dict[str, GoogleAirQualityUpdateCoordinator] = {}
    for subentry_id in entry.subentries:
        coordinators[subentry_id] = GoogleAirQualityUpdateCoordinator(
            hass, entry, subentry_id, api_client
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
