"""The Google Air Quality integration."""

import asyncio

from google_air_quality_api.api import GoogleAirQualityApi
from google_air_quality_api.auth import Auth

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFERRER
from .coordinator import (
    GoogleAirQualityConfigEntry,
    GoogleAirQualityCurrentConditionsCoordinator,
    GoogleAirQualityForecastCoordinator,
    GoogleAirQualityRuntimeData,
    GoogleAirQualitySubEntryRuntimeData,
)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: GoogleAirQualityConfigEntry
) -> bool:
    """Set up Google Air Quality from a config entry."""
    session = async_get_clientsession(hass)
    api_key = entry.data[CONF_API_KEY]
    referrer = entry.data.get(CONF_REFERRER)
    auth = Auth(session, api_key, referrer=referrer)
    client = GoogleAirQualityApi(auth)
    subentries_runtime_data: dict[str, GoogleAirQualitySubEntryRuntimeData] = {}
    for subentry_id in entry.subentries:
        subentry_runtime_data = GoogleAirQualitySubEntryRuntimeData(
            coordinator_current_conditions=GoogleAirQualityCurrentConditionsCoordinator(
                hass, entry, subentry_id, client
            ),
            coordinator_forecast=GoogleAirQualityForecastCoordinator(
                hass, entry, subentry_id, client
            ),
        )
        subentries_runtime_data[subentry_id] = subentry_runtime_data
    tasks = [
        coro
        for subentry_runtime_data in subentries_runtime_data.values()
        for coro in (
            subentry_runtime_data.coordinator_current_conditions.async_config_entry_first_refresh(),
            subentry_runtime_data.coordinator_forecast.async_config_entry_first_refresh(),
        )
    ]
    await asyncio.gather(*tasks)
    entry.runtime_data = GoogleAirQualityRuntimeData(
        api=client,
        subentries_runtime_data=subentries_runtime_data,
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
